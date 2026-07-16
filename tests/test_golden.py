"""Golden-file regression tests.

Compares a freshly built pipeline against the committed reference files in
tests/golden/fixtures/. A failure here after a compas_dem bump means
upstream changed behaviour — investigate, then either fix or intentionally
regenerate the goldens (python tests/golden/generate.py) and commit the diff.

Skipped entirely until the fixtures have been generated once.
"""

import pathlib

import compas
import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")  # loading BlockModel JSON imports it

FIXTURES = pathlib.Path(__file__).parent / "golden" / "fixtures"

pytestmark = pytest.mark.skipif(
    not (FIXTURES / "arch_model.json").exists(),
    reason="golden fixtures not generated yet (run: python tests/golden/generate.py)",
)


@pytest.fixture(scope="module")
def golden_model():
    return compas.json_load(FIXTURES / "arch_model.json")


def test_fresh_model_matches_golden(golden_model):
    import sys

    sys.path.insert(0, str(FIXTURES.parent))
    from generate import build_model

    fresh = build_model()
    assert len(list(fresh.elements())) == len(list(golden_model.elements()))
    assert len(list(fresh.contacts())) == len(list(golden_model.contacts()))
    assert len(list(fresh.supports())) == len(list(golden_model.supports()))


def test_golden_problem_links_golden_model(golden_model):
    problem = compas.json_load(FIXTURES / "arch_problem.json")
    assert problem.model_id == str(golden_model.guid)


def test_golden_results_link_model_and_problem(golden_model):
    filepath = FIXTURES / "arch_results.json"
    if not filepath.exists():
        pytest.skip("arch_results.json not generated (solver backend missing)")
    results = compas.json_load(filepath)
    problem = compas.json_load(FIXTURES / "arch_problem.json")
    assert results.model_id == str(golden_model.guid)
    assert results.problem_id == str(problem.guid)
    assert all(results.force_magnitude(e) is not None for e in results.edges())
