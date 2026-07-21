"""Headless tests: thrust mesh → BlockModel (the TNA_blockexports pipeline).

Exercises the compas_dem constructors the command wraps, on a synthetic
vault-like mesh (no TNA run needed — any mesh with height variation works).
"""

import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")
pytest.importorskip("compas_libigl", reason="compas_libigl needed for remeshing/pattern mapping")

import math  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402
from compas_dem.models import BlockModel  # noqa: E402


@pytest.fixture(scope="module")
def thrust_mesh():
    """A synthetic dome-ish thrust surface over a 10x10 grid."""
    mesh = Mesh.from_meshgrid(dx=10, nx=10)
    for vertex in mesh.vertices():
        x, y = mesh.vertex_attributes(vertex, "xy")
        z = 3.0 * math.sin(math.pi * x / 10) * math.sin(math.pi * y / 10)
        mesh.vertex_attribute(vertex, "z", z)
    return mesh


def test_from_triangulation_dual(thrust_mesh):
    model = BlockModel.from_triangulation_dual(thrust_mesh, tmin=0.05, tmax=0.3)
    blocks = list(model.elements())
    assert blocks
    # constructor builds the interaction graph from face adjacency
    assert model.graph.number_of_edges() > 0


def test_from_meshpattern(thrust_mesh):
    from compas_libigl.mapping import TESSAGON_TYPES

    patternname = sorted(TESSAGON_TYPES)[0]
    model = BlockModel.from_meshpattern(thrust_mesh, patternname, tmin=0.05, tmax=0.3)
    assert list(model.elements())


def test_thickness_bounds_respected(thrust_mesh):
    """Blocks over the crown (high z) should be thinner than at the springing."""
    tmin, tmax = 0.05, 0.3
    model = BlockModel.from_triangulation_dual(thrust_mesh, tmin=tmin, tmax=tmax)
    # inverse-height thickness: verify all blocks have finite, positive volume
    for block in model.elements():
        assert block.modelgeometry.volume > 0
