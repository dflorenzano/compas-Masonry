"""Headless tests: Problem setup, solver attachment, serialization.

This is the contract the Problem-group commands rely on. Rewritten for the
2026-08 compas_dem restructure — the shape of every one of these changed:

- supports live on the MODEL (`model.add_supports`), never on the problem
- there is no gravity call: self-weight is applied unconditionally from density
- `problem.solve()` replaces `model.solve(problem)`
- `set_solver` / `set_contact_model` replace `solver()` / `add_contact_model()`
- a problem serializes as a guid REFERENCE to its model, and `Analysis` is what
  hands the model back on load
"""

import compas
import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")  # BlockModel hard-imports it

from compas_dem.models import Analysis  # noqa: E402
from compas_dem.problem import PointLoad  # noqa: E402
from compas_dem.problem import Problem  # noqa: E402
from compas_dem.problem import Translation  # noqa: E402
from compas_dem.problem.solvers import Solver  # noqa: E402


@pytest.fixture
def supported_arch(arch_model):
    """An arch with both springings marked as supports, on the MODEL."""
    nodes = list(arch_model.graph.nodes())
    arch_model.add_supports([nodes[0], nodes[-1]])
    return arch_model


@pytest.fixture
def problem(supported_arch):
    return Problem(supported_arch, name="Problem_1")


def test_problem_links_model_by_guid(problem, supported_arch):
    assert problem.model_guid == str(supported_arch.guid)


def test_supports_live_on_the_model_not_the_problem(problem, supported_arch):
    """`add_supports_from_model` is gone: supports were copied onto the problem
    and into every BC, so editing them left stale copies with nothing to say so.
    The solvers read `Block.is_support` directly now."""
    assert not hasattr(problem, "add_supports_from_model")
    assert not hasattr(problem, "supports")
    assert sum(1 for b in supported_arch.elements() if b.is_support) == 2


def test_solve_without_solver_raises(problem):
    with pytest.raises(ValueError, match="[Nn]o solver"):
        problem.solve()


def test_solver_attach(problem):
    problem.set_solver(Solver.CRA())
    assert problem.solver.name == "CRA"


def test_contact_model(problem):
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    assert problem.contact_properties is not None  # a property, not a method


def test_loads_and_displacements_are_typed_and_partitioned(problem):
    """A BC is a typed object; `loads` and `displacements` partition them by
    class. That is what replaced the session-side BC-kind map."""
    problem.add(PointLoad.at_face(block=1, face=0, force=[0, 0, -1000]))
    problem.add(Translation(block=2, dz=-0.01))

    assert len(problem.boundary_conditions) == 2
    assert [type(bc).__name__ for bc in problem.loads] == ["PointLoad"]
    assert [type(bc).__name__ for bc in problem.displacements] == ["Translation"]


def test_problem_json_roundtrip(tmp_path, problem):
    """A problem writes a guid reference, never the model itself."""
    problem.add(PointLoad.at_face(block=1, face=0, force=[0, 0, -1000], name="Wind"))

    filepath = tmp_path / "problem.json"
    compas.json_dump(problem, filepath)
    loaded = compas.json_load(filepath)

    assert loaded.model_guid == problem.model_guid
    assert len(loaded.boundary_conditions) == 1
    # the group name rides in the Data envelope, not in __data__ — the plugin
    # groups its layers by it, so a silent loss here would collapse the tree
    assert loaded.boundary_conditions[0].name == "Wind"


def test_analysis_writes_the_model_once_and_rebinds_it(tmp_path, supported_arch, problem):
    """`Analysis` owns model + problems; a reloaded problem can solve without
    the caller re-attaching the model by hand."""
    analysis = Analysis(supported_arch, name="study")
    analysis.add_problem(problem)

    filepath = tmp_path / "analysis.json"
    compas.json_dump(analysis, filepath)
    loaded = compas.json_load(filepath)

    assert loaded.model is not None
    assert loaded.problems[0].model.guid == loaded.model.guid


def test_solve_cra(arch_model_with_contacts):
    """End-to-end solve. Skipped unless a CRA backend is installed."""
    pytest.importorskip("compas_cra", reason="compas_cra not installed (optional solver dep)")

    nodes = list(arch_model_with_contacts.graph.nodes())
    arch_model_with_contacts.add_supports([nodes[0], nodes[-1]])

    problem = Problem(arch_model_with_contacts, name="Problem_CRA")
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    problem.set_solver(Solver.CRA())

    results = problem.solve()

    assert results.model_id == str(arch_model_with_contacts.guid)
    assert results.problem_id == str(problem.guid)
    # every contact edge should carry a force after solving
    edges = list(results.edges())
    assert edges
    assert all(results.force_magnitude(e) is not None for e in edges)


def test_cra_refuses_a_prescribed_movement(arch_model_with_contacts):
    """CRA/RBE exclude support blocks from the equilibrium system, so they have
    no displacement DOFs and cannot express a settlement. compas_dem refuses
    rather than returning a self-weight answer for a different problem —
    Problem_solve checks for this before calling."""
    pytest.importorskip("compas_cra", reason="compas_cra not installed (optional solver dep)")

    nodes = list(arch_model_with_contacts.graph.nodes())
    arch_model_with_contacts.add_supports([nodes[0], nodes[-1]])

    problem = Problem(arch_model_with_contacts, name="Problem_settlement")
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    problem.set_solver(Solver.CRA())
    problem.add(Translation(block=nodes[0], dz=-0.01))

    with pytest.raises(ValueError, match="displacement"):
        problem.solve()
