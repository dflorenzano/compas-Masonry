"""Headless tests for the pure logic inside the commands and the session.

These need no Rhino: `rhinostub` fakes the imports so a `commands/CM_*.py`
module can be loaded, and everything exercised here is plain data handling.
"""

import pathlib

import pytest

from rhinostub import command_path, load_command

COMMANDS = pathlib.Path(__file__).resolve().parents[1] / "commands"


@pytest.fixture(scope="module")
def addload():
    return load_command(command_path("Problem_addload"), "addload")


@pytest.fixture
def session():
    """A dict-shaped stand-in for MasonrySession.

    The BC-kind helpers only use the session's mapping behaviour, so binding
    them onto a dict exercises the real implementations without Rhino.
    """
    from compas_masonry.session import MasonrySession

    class FakeSession(dict):
        BC_KINDS = MasonrySession.BC_KINDS
        BC_KIND_DEFAULT = MasonrySession.BC_KIND_DEFAULT
        BC_KIND_ACCEPTS = MasonrySession.BC_KIND_ACCEPTS
        bc_allows = MasonrySession.bc_allows
        bc_kind = MasonrySession.bc_kind
        bc_kinds = MasonrySession.bc_kinds
        set_bc_kind = MasonrySession.set_bc_kind
        reindex_bc_kinds = MasonrySession.reindex_bc_kinds

        def setdefault(self, key, factory):
            if key not in self:
                self[key] = factory() if callable(factory) else factory
            return self[key]

    return FakeSession()


# =============================================================================
# Surface loads over several faces
# =============================================================================


@pytest.mark.parametrize(
    "text, nfaces, expected",
    [
        ("0", 6, ([0], [])),
        ("0,3,5", 6, ([0, 3, 5], [])),
        ("0 3 5", 6, ([0, 3, 5], [])),
        ("5,3,0", 6, ([0, 3, 5], [])),  # sorted
        ("3,3,3", 6, ([3], [])),  # de-duplicated
        ("all", 6, ([0, 1, 2, 3, 4, 5], [])),
        ("ALL", 4, ([0, 1, 2, 3], [])),
        ("*", 3, ([0, 1, 2], [])),
        ("", 6, ([], [])),
        ("   ", 6, ([], [])),
    ],
)
def test_parse_faces_accepts(addload, text, nfaces, expected):
    assert addload.parse_faces(text, nfaces) == expected


@pytest.mark.parametrize(
    "text, nfaces, expected",
    [
        ("0,9", 6, ([0], ["9"])),  # out of range dropped, the valid one kept
        ("-1,2", 6, ([2], ["-1"])),
        ("x,2", 6, ([2], ["x"])),
        ("9", 6, ([], ["9"])),
    ],
)
def test_parse_faces_rejects(addload, text, nfaces, expected):
    """Bad entries are reported, never silently turned into the wrong face."""
    assert addload.parse_faces(text, nfaces) == expected


# =============================================================================
# Boundary condition kinds
# =============================================================================


@pytest.mark.parametrize(
    "kind, entry, allowed",
    [
        ("Gravity", "gravity", True),
        ("Gravity", "load", False),
        ("Gravity", "displacement", False),
        ("Loads", "load", True),
        ("Loads", "gravity", False),
        ("Loads", "displacement", False),
        ("Displacements", "displacement", True),
        ("Displacements", "load", False),
        ("Displacements", "gravity", False),
        ("Mixed", "gravity", True),
        ("Mixed", "load", True),
        ("Mixed", "displacement", True),
    ],
)
def test_bc_allows(session, kind, entry, allowed):
    assert session.bc_allows(kind, entry) is allowed


def test_bc_kind_defaults_to_mixed(session):
    """A BC that never had a kind set stays permissive rather than blocking edits."""
    session.set_bc_kind("P", 0, "Gravity")
    assert session.bc_kind("P", 0) == "Gravity"
    assert session.bc_kind("P", 7) == "Mixed"
    assert session.bc_kind("Unknown", 0) == "Mixed"


def test_reindex_bc_kinds_after_delete(session):
    """The kind map is keyed by index, so it has to shift when a BC is removed."""
    for index, kind in enumerate(["Gravity", "Loads", "Displacements"]):
        session.set_bc_kind("P", index, kind)

    session.reindex_bc_kinds("P", [0, 2])  # BC at index 1 deleted

    assert session["bc_kinds"]["P"] == {"0": "Gravity", "1": "Displacements"}


# =============================================================================
# Body forces (tilted table / static seismic)
# =============================================================================


def test_unit_vector(addload):
    assert addload.unit([2.0, 0.0, 0.0]) == [1.0, 0.0, 0.0]
    assert addload.unit([0.0, 0.0, 0.0]) is None  # zero-length is rejected, not divided by


def test_body_force_is_mass_times_acceleration(addload):
    """Every block gets a centroid point load of mass * a along the direction."""
    pytest.importorskip("compas_dem")
    from compas_dem.material import Stone
    from compas_dem.models import BlockModel
    from compas_dem.problem import BoundaryCondition
    from compas_dem.templates import ArchTemplate

    model = BlockModel.from_template(ArchTemplate(rise=3.0, span=10.0, thickness=0.7, depth=0.5, n=5))
    material = Stone.from_predefined_material("CONCRETE C20/25")
    model.add_material(material)
    model.assign_material(material, elements=list(model.elements()))

    bc = BoundaryCondition(name="Seismic")
    assert addload.add_body_force(None, model, bc, 2.0, [1.0, 0.0, 0.0], "ramp") is True

    loads = bc.point_loads
    assert len(loads) == model.graph.number_of_nodes()

    blocks = {b.graphnode: b for b in model.elements()}
    for entry in loads:
        block = blocks[entry["block_index"]]
        expected = material.density * block.modelgeometry.volume() * 2.0
        assert entry["force"][0] == pytest.approx(expected)
        assert entry["force"][1] == pytest.approx(0.0)
        assert entry["force"][2] == pytest.approx(0.0)


def test_body_force_needs_a_density(addload):
    """Without an assigned material there is no mass, so nothing is applied."""
    pytest.importorskip("compas_dem")
    from compas_dem.models import BlockModel
    from compas_dem.problem import BoundaryCondition
    from compas_dem.templates import ArchTemplate

    model = BlockModel.from_template(ArchTemplate(rise=3.0, span=10.0, thickness=0.7, depth=0.5, n=3))
    bc = BoundaryCondition()

    assert addload.add_body_force(None, model, bc, 2.0, [1.0, 0.0, 0.0], "ramp") is False
    assert bc.point_loads == []


def test_body_force_rejects_a_zero_direction(addload):
    pytest.importorskip("compas_dem")
    from compas_dem.problem import BoundaryCondition

    class FakeModel:
        def elements(self):
            return iter(())

    assert addload.add_body_force(None, FakeModel(), BoundaryCondition(), 1.0, [0.0, 0.0, 0.0], "ramp") is False


# =============================================================================
# Result keys
# =============================================================================


def test_result_key_names_solver_and_bcs():
    solve = load_command(command_path("Problem_solve"), "solve")
    assert solve.result_key("RBE", ["BC1"]) == "RBE_BC1"
    assert solve.result_key("CRA", ["BC1", "BC2"]) == "CRA_BC1-BC2"


# =============================================================================
# Refreshing supports after the model changes
# =============================================================================


def test_refresh_problem_supports_keeps_prescribed_displacements():
    """Re-importing supports must replace ONLY the full-fixity entries.

    Supports are mirrored into every BC, so a naive rewrite would also wipe a
    settlement prescribed on one of those same blocks.
    """
    pytest.importorskip("compas_dem")
    from compas_dem.models import BlockModel
    from compas_dem.problem import BoundaryCondition, Problem
    from compas_dem.templates import ArchTemplate

    from compas_masonry.session import MasonrySession

    model = BlockModel.from_template(ArchTemplate(rise=3.0, span=10.0, thickness=0.7, depth=0.5, n=5))
    blocks = list(model.elements())
    blocks[0].is_support = True

    problem = Problem(model, name="P")
    problem.add_supports_from_model(model)
    bc = BoundaryCondition(name="BC1")
    problem.add_boundary_condition(bc)
    bc.add_displacement(2, dz=-0.01)  # a settlement that must survive

    class FakeSession(dict):
        refresh_problem_supports = MasonrySession.refresh_problem_supports

        @property
        def problems(self):
            return {"P": problem}

        def save_problems(self):
            pass

        def get(self, key, default=None):
            return model if key == "blockmodel" else default

    session = FakeSession()

    # the model's supports change after the problem was built
    blocks[0].is_support = False
    blocks[-1].is_support = True

    before, after = session.refresh_problem_supports("P", model)

    assert before == [blocks[0].graphnode]
    assert after == [blocks[-1].graphnode]
    assert problem.supports == after

    from compas_masonry.boundaryconditions import is_support

    supports = [e for e in bc.displacements if is_support(e)]
    prescribed = [e for e in bc.displacements if not is_support(e)]

    assert [e["block_index"] for e in supports] == after
    assert len(prescribed) == 1 and prescribed[0]["translation"] == [None, None, -0.01]


# =============================================================================
# BC naming
# =============================================================================


def test_bc_name_falls_back_past_the_class_name():
    """compas `Data.name` returns the CLASS NAME when unset, so an unnamed BC
    reports "BoundaryCondition" and would never reach the "BC<n>" default."""
    pytest.importorskip("compas_dem")
    from compas_dem.problem import BoundaryCondition

    from compas_masonry.boundaryconditions import bc_name

    unnamed = BoundaryCondition()
    assert unnamed.name == "BoundaryCondition"  # the trap this guards against
    assert bc_name(unnamed, 1) == "BC2"

    assert bc_name(BoundaryCondition(name="Live"), 0) == "Live"
