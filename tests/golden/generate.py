"""Generate golden reference files for plugin testing.

Run OUTSIDE Rhino, from the repo root:

    python tests/golden/generate.py

Produces in tests/golden/fixtures/:
    arch_model.json     BlockModel with contacts + supports
    arch_problem.json   Problem (gravity, supports, CRA solver attached)
    arch_results.json   Results (only if a CRA backend is installed)

Uses:
1. pytest (test_golden.py) asserts the pipeline still reproduces these
   when compas_dem is bumped — catches upstream regressions.
2. In Rhino, load them through the import commands to test DRAWING
   without re-running analysis: if the plugin renders a golden results
   file correctly, the scene code works.

Regenerate (and commit) only when an intentional upstream change alters
the outputs. Review the diff — that IS the regression report.
"""

import pathlib

import compas
from compas_dem.models import BlockModel
from compas_dem.problem import Problem
from compas_dem.problem.solvers import Solver
from compas_dem.templates import ArchTemplate

HERE = pathlib.Path(__file__).parent
FIXTURES = HERE / "fixtures"
FIXTURES.mkdir(exist_ok=True)


def build_model() -> BlockModel:
    template = ArchTemplate(rise=3.0, span=10.0, thickness=0.5, depth=0.5, n=20)
    model = BlockModel.from_template(template)

    nodes = list(model.graph.nodes())
    model.graph.node_element(nodes[0]).is_support = True
    model.graph.node_element(nodes[-1]).is_support = True

    model.compute_contacts(tolerance=1e-6, minimum_area=0.01)
    return model


def build_problem(model: BlockModel) -> Problem:
    problem = Problem(model, name="Problem_1")
    # supports live on the model; self-weight is applied unconditionally, and CRA
    # reads no boundary conditions at all — so the problem carries none
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    problem.set_solver(Solver.CRA())
    return problem


def main():
    model = build_model()
    compas.json_dump(model, FIXTURES / "arch_model.json")
    print(f"arch_model.json      blocks={len(list(model.elements()))} contacts={len(list(model.contacts()))}")

    problem = build_problem(model)
    compas.json_dump(problem, FIXTURES / "arch_problem.json")
    print(f"arch_problem.json    model_id={problem.model_id}")

    try:
        results = problem.solve()
    except ImportError as e:
        print(f"arch_results.json    SKIPPED (solver backend not installed: {e})")
        return
    compas.json_dump(results, FIXTURES / "arch_results.json")
    print(f"arch_results.json    edges={len(list(results.edges()))}")


if __name__ == "__main__":
    main()
