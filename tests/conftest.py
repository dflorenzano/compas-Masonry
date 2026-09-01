"""Shared fixtures for headless (no-Rhino) tests.

These tests exercise the compas_dem pipeline that the plugin commands wrap.
They require compas, compas_model, compas_dem (and compas_cgal/compas_libigl
for contact detection). Run with plain pytest from the repo root:

    pytest tests/
"""

import pathlib
import sys

import pytest

# conftest is imported before any test module, so this is what makes the
# sibling helper modules (rhinostub) importable by name regardless of pytest's
# import mode.
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# NOTE: dependency skips live at the top of each test module (importorskip in
# conftest would turn missing deps into collection errors instead of skips).


@pytest.fixture
def arch_model():
    """A small arch BlockModel — the canonical test assembly."""
    from compas_dem.models import BlockModel
    from compas_dem.templates import ArchTemplate

    template = ArchTemplate(rise=3.0, span=10.0, thickness=0.5, depth=0.5, n=20)
    return BlockModel.from_template(template)


@pytest.fixture
def arch_model_with_contacts(arch_model):
    arch_model.compute_contacts(tolerance=1e-6, minimum_area=0.01)
    return arch_model
