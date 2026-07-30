"""Headless tests: Problem setup, solver attachment, serialization.

This is the contract the Problem-group commands rely on.
"""

import compas
import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")  # BlockModel hard-imports it

from compas_dem.problem import Problem  # noqa: E402
from compas_dem.problem.solvers import Solver  # noqa: E402


@pytest.fixture
def problem(arch_model):
    nodes = list(arch_model.graph.nodes())
    arch_model.graph.node_element(nodes[0]).is_support = True
    arch_model.graph.node_element(nodes[-1]).is_support = True

    problem = Problem(arch_model, name="Problem_1")
    problem.add_gravity()
    problem.add_supports_from_model(arch_model)
    return problem


def test_problem_links_model_by_guid(problem, arch_model):
    assert problem.model_id == str(arch_model.guid)


def test_solve_without_solver_raises(problem, arch_model):
    with pytest.raises(ValueError, match="No solver configured"):
        arch_model.solve(problem)


def test_solver_attach(problem):
    problem.solver(Solver.CRA())
    assert problem._solver.name == "CRA"


def test_contact_model(problem):
    problem.add_contact_model("MohrCoulomb", mu=0.6)
    assert problem.contact_properties is not None  # a property, not a method


def test_problem_json_roundtrip(tmp_path, problem):
    filepath = tmp_path / "problem.json"
    compas.json_dump(problem, filepath)
    loaded = compas.json_load(filepath)
    assert loaded.model_id == problem.model_id


def test_model_validity_check_rejects_wrong_model(problem):
    """A problem must refuse to run against a model it wasn't built for."""
    from compas_dem.models import BlockModel
    from compas_dem.templates import ArchTemplate

    other = BlockModel.from_template(ArchTemplate(rise=2.0, span=6.0, thickness=0.4, depth=0.5, n=10))
    with pytest.raises(Exception):
        problem.check_model_validity(other)


def test_solve_cra(arch_model_with_contacts):
    """End-to-end solve. Skipped unless a CRA backend is installed."""
    pytest.importorskip("compas_cra", reason="compas_cra not installed (optional solver dep)")

    nodes = list(arch_model_with_contacts.graph.nodes())
    arch_model_with_contacts.graph.node_element(nodes[0]).is_support = True
    arch_model_with_contacts.graph.node_element(nodes[-1]).is_support = True

    problem = Problem(arch_model_with_contacts, name="Problem_CRA")
    problem.add_gravity()
    problem.add_supports_from_model(arch_model_with_contacts)
    problem.solver(Solver.CRA())

    results = arch_model_with_contacts.solve(problem)

    assert results.model_id == str(arch_model_with_contacts.guid)
    assert results.problem_id == str(problem.guid)
    # every contact edge should carry a force after solving
    edges = list(results.edges())
    assert edges
    assert all(results.force_magnitude(e) is not None for e in edges)
