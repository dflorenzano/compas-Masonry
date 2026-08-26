"""Headless tests: Problem setup, solver attachment, serialization.

This is the contract the Problem-group commands rely on. Rewritten for the
2026-08 compas_dem restructure — the shape of every one of these changed:

- supports live on the MODEL (`model.add_supports`), never on the problem
- there is no gravity call: self-weight is applied unconditionally from density
- `problem.solve()` replaces `model.solve(problem)`
- `set_solver` / `set_contact_model` replace `solver()` / `add_contact_model()`
- a problem serializes as a guid REFERENCE to its model, and `Analysis` is what
  hands the model back on load

Updated 2026-08-07 for `BoundaryConditionGroup`: a Problem holds GROUPS, and the
typed conditions live inside them. `problem.add()`, `problem.loads`,
`problem.displacements` and `problem.solver` are all gone.
"""

import compas
import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")  # BlockModel hard-imports it

from compas_dem.models import Analysis  # noqa: E402
from compas_dem.problem import Problem  # noqa: E402
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
    assert problem.model_id == str(supported_arch.guid)


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
    """compas_dem has `set_solver()` but NO public getter, so the plugin reads it
    through `MasonrySession.solver_of` — the one place that touches `_solver`."""
    from compas_masonry.session import MasonrySession

    assert not hasattr(type(problem), "solver")
    problem.set_solver(Solver.CRA())
    assert MasonrySession.solver_of(problem).name == "CRA"


def test_contact_model(problem):
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    assert problem.contact_properties is not None  # a property, not a method


def test_conditions_live_inside_groups(problem):
    """`boundary_conditions` is a list of GROUPS, and the typed objects hang off
    each group by kind. `problem.loads` / `problem.displacements` are gone."""
    assert not hasattr(type(problem), "loads")
    assert not hasattr(type(problem), "displacements")
    assert not hasattr(problem, "add")

    group = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_face(block_index=1, face_index=0, force=[0, 0, -1000], boundary_condition=group)
    problem.add_displacement(block_index=2, displacement=[None, None, -0.01], boundary_condition=group)

    assert len(problem.boundary_conditions) == 1
    assert [type(bc).__name__ for bc in group.point_loads] == ["PointLoad"]
    assert [type(bc).__name__ for bc in group.displacements] == ["Translation"]
    # a component left None stays unconstrained — never coerced to a prescribed 0.0
    assert group.displacements[0].translation == [None, None, -0.01]


def test_a_boundary_condition_needs_a_group(problem):
    """Every `Problem.add_*` requires `boundary_condition=`; there is no default
    group, and omitting it raises rather than inventing one."""
    with pytest.raises(ValueError, match="[Nn]o boundary condition"):
        problem.add_point_load_at_centroid(block_index=1, force=[0, 0, -1])


def test_group_names_are_unique_per_problem(problem):
    """Names are unique across the whole problem, load and displacement alike —
    which is why `next_group_name` counts over every group, not one kind."""
    problem.add_boundary_condition("Wind")
    with pytest.raises(ValueError, match="already registered"):
        problem.add_boundary_condition("Wind")


def test_problem_json_roundtrip(tmp_path, problem):
    """A problem writes a guid reference, never the model itself — and comes back
    UNBOUND. `problem.model` raising is the reason the session stores an Analysis
    rather than the model and the problems separately."""
    group = problem.add_boundary_condition("Wind")
    problem.add_point_load_at_face(block_index=1, face_index=0, force=[0, 0, -1000], boundary_condition=group)

    filepath = tmp_path / "problem.json"
    compas.json_dump(problem, filepath)
    loaded = compas.json_load(filepath)

    assert loaded.model_id == problem.model_id
    with pytest.raises(ValueError, match="[Nn]o model loaded"):
        loaded.model

    assert len(loaded.boundary_conditions) == 1
    # the group name is part of the group's own __data__ now, and the plugin
    # names a Rhino layer after it — a silent loss would collapse the tree
    assert loaded.boundary_conditions[0].name == "Wind"
    assert len(loaded.boundary_conditions[0].point_loads) == 1


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

    from compas_dem.material.generic import GenericMaterial

    material = GenericMaterial(density=2500, Ecm=1e9)
    arch_model_with_contacts.add_material(material)
    for block in arch_model_with_contacts.elements():
        arch_model_with_contacts.assign_material(material, element=block)

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


def test_cra_ignores_boundary_conditions_rather_than_refusing_them():
    """**CRA does not refuse a boundary condition — it never looks at one.**

    This test used to assert the opposite, and was wrong: it asserted that
    compas_dem raises for a prescribed movement under CRA. `cra_solve` and
    `rbe_solve` take (problem, model, mu, density, d_bnd, eps, verbose, timer) and
    read `problem.boundary_conditions` nowhere, so a settlement or a point load
    comes back as a self-weight answer that looks like a result.

    Nothing downstream catches that, which is why the refusal lives in
    Problem_solve — see `test_solve_refuses_cra_on_a_problem_with_boundary_conditions`
    in test_command_helpers.py. Pinned by signature here so it needs no backend.
    """
    import inspect

    # compas_dem.analysis.cra hard-imports compas_cra at module level
    pytest.importorskip("compas_cra", reason="compas_cra not installed (optional solver dep)")
    from compas_dem.analysis.cra import cra_solve, rbe_solve

    for func in (cra_solve, rbe_solve):
        params = set(inspect.signature(func).parameters)
        assert "loads" not in params, f"{func.__name__} takes loads= again — the command guard can be revisited"
        source = inspect.getsource(func)
        assert "boundary_condition" not in source, f"{func.__name__} reads boundary conditions now"
