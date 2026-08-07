"""Headless tests for the pure logic inside the commands and the session.

These need no Rhino: `rhinostub` fakes the imports so a `commands/CM_*.py`
module can be loaded, and everything exercised here is plain data handling.
"""

import pathlib

import pytest

from rhinostub import command_path, load_command

COMMANDS = pathlib.Path(__file__).resolve().parents[1] / "commands"


@pytest.fixture(scope="module")
def loads():
    return load_command(command_path("Problem_loads"), "loads")


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
def test_parse_faces_accepts(loads, text, nfaces, expected):
    assert loads.parse_faces(text, nfaces) == expected


@pytest.mark.parametrize(
    "text, nfaces, expected",
    [
        ("0,9", 6, ([0], ["9"])),  # out of range dropped, the valid one kept
        ("-1,2", 6, ([2], ["-1"])),
        ("x,2", 6, ([2], ["x"])),
        ("9", 6, ([], ["9"])),
    ],
)
def test_parse_faces_rejects(loads, text, nfaces, expected):
    """Bad entries are reported, never silently turned into the wrong face."""
    assert loads.parse_faces(text, nfaces) == expected


# =============================================================================
# Body forces (tilted table / static seismic)
# =============================================================================

# The plugin used to expand a BodyForce into one centroid point load per block,
# because `add_global_body_force` reached no solver. compas_dem's
# `resolve_centroidal_loads` now applies `BodyForce` natively and mass-weights it
# (`a_vec * _element_mass(block)`), so the expansion and its helpers (`block_mass`,
# `unit`, `add_body_force`) are gone, and the tests that pinned them with it.


# =============================================================================
# Result keys
# =============================================================================


def test_result_key_is_solver_plus_timestamp():
    """A problem IS the load case, so no BC names are left to key by.

    The timestamp keeps a re-solve beside the earlier run rather than
    overwriting it, and must carry no colon: the key becomes a layer name.
    """
    import re

    solve = load_command(command_path("Problem_solve"), "solve")

    key = solve.result_key("RBE")
    assert re.match(r"^RBE_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$", key), key
    assert ":" not in key


def test_solve_refuses_cra_on_a_problem_with_boundary_conditions():
    """CRA and RBE never read `problem.boundary_conditions` — they solve
    self-weight equilibrium. So a problem carrying loads does not fail under CRA,
    it returns a plausible answer that ignored them. Nothing downstream catches
    that, which is why the guard lives in the command.

    (This replaced `cra_accepts_loads`, which probed compas_cra for a `loads=`
    parameter compas_dem no longer passes.)
    """
    pytest.importorskip("compas_dem")
    pytest.importorskip("compas_cgal")

    from compas_dem.models import BlockModel
    from compas_dem.problem import Problem, Solver
    from compas_dem.templates import ArchTemplate

    solve = load_command(command_path("Problem_solve"), "solve")
    assert not hasattr(solve, "cra_accepts_loads")

    model = BlockModel.from_template(ArchTemplate(rise=3.0, span=10.0, thickness=0.5, depth=0.5, n=6))
    model.compute_contacts(tolerance=1e-6, minimum_area=0.01)
    nodes = list(model.graph.nodes())
    model.add_supports([nodes[0], nodes[-1]])

    problem = Problem(model, name="P1")
    problem.set_contact_model("MohrCoulomb", mu=0.6)
    problem.set_solver(Solver.CRA())

    # nothing to ignore yet, so CRA is fine (a material check may still bite —
    # what matters is that it is NOT the boundary-condition message)
    assert "applies none of them" not in (solve.check_ready(model, problem, "P1") or "")

    group = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=2, force=[0, 0, -1000], boundary_condition=group)

    message = solve.check_ready(model, problem, "P1")
    assert message and "applies none of them" in message
    assert "Load_1" in message

    # LMGC90 does apply them, so the same problem passes this check
    problem.set_solver(Solver.LMGC90(duration=1.0, n_steps=100))
    assert "applies none of them" not in (solve.check_ready(model, problem, "P1") or "")


def test_lmgc90_solver_never_gets_verbose_zero():
    """For LMGC90 `verbose` is a print INTERVAL, not a flag: `lmgc90_solve` does
    `step % verbose`, so the old Quiet toggle sent 0 and every solve died with
    ZeroDivisionError. The command stops passing it at all."""
    pytest.importorskip("compas_dem")

    setsolver = load_command(command_path("Problem_setsolver"), "setsolver")
    source = pathlib.Path(command_path("Problem_setsolver")).read_text()

    assert "verbose=int(verbose)" not in source
    assert setsolver.Solver.LMGC90(duration=1.0, n_steps=100).parameters["verbose"] != 0


# =============================================================================
# Layer paths
# =============================================================================


@pytest.fixture
def layers():
    """A stand-in exposing the pure layer-path helpers of MasonrySession.

    They are string builders over `self.problems`, so binding them onto a class
    with a problems dict exercises the real implementations without Rhino.
    """
    from compas_masonry.session import MasonrySession

    class FakeLayers:
        BC_PARENT_LAYER = MasonrySession.BC_PARENT_LAYER
        RESULTS_LAYER = MasonrySession.RESULTS_LAYER
        problem_index = MasonrySession.problem_index
        indexed_problem_layer = MasonrySession.indexed_problem_layer
        bc_parent_layer = MasonrySession.bc_parent_layer
        bc_layer = MasonrySession.bc_layer
        results_layer = MasonrySession.results_layer

        problems = {"arch": object(), "dome": object()}

    return FakeLayers()


def test_condition_groups_hang_off_a_parent_layer(layers):
    """Conditions share one BoundaryConditions layer, one sublayer per GROUP.

    The BC<n>_<name> level is gone: a problem IS the load case, so there is no
    container to name — the group is the condition's own name.
    """
    assert layers.bc_parent_layer("arch") == "Masonry::1_arch::BoundaryConditions"
    assert layers.bc_layer("arch") == "Masonry::1_arch::BoundaryConditions"
    assert layers.bc_layer("arch", "Load_1") == "Masonry::1_arch::BoundaryConditions::Load_1"
    assert layers.bc_layer("dome", "Wind") == "Masonry::2_dome::BoundaryConditions::Wind"


def test_results_live_at_problem_level(layers):
    """A result set covers a COMBINATION of BCs, so it belongs to the problem.

    Filing it under one BC meant choosing which of them to blame, and losing the
    set when that BC was renamed or deleted.
    """
    assert layers.results_layer("arch") == "Masonry::1_arch::Results"
    assert layers.results_layer("arch", "RBE_BC1-BC2") == "Masonry::1_arch::Results::RBE_BC1-BC2"
    assert layers.results_layer("arch", "RBE_BC1-BC2", "Forces") == "Masonry::1_arch::Results::RBE_BC1-BC2::Forces"
    assert layers.results_layer("arch", "CRA_BC1", "Displaced") == "Masonry::1_arch::Results::CRA_BC1::Displaced"

    # a results layer is never a descendant of the BC parent layer
    assert layers.BC_PARENT_LAYER not in layers.results_layer("arch", "RBE_BC1")


def test_condition_group_layers_are_discovered_not_declared():
    """There is no fixed list of condition sublayers any more.

    A group layer is named after the conditions it holds ("Load_1", "Wind"), so
    the set has to come from the problem. A hardcoded BC_SUBLAYERS would have
    silently capped every problem at two groups.
    """
    from compas_masonry.session import MasonrySession

    assert not hasattr(MasonrySession, "BC_SUBLAYERS")
    assert MasonrySession.BC_PARENT_LAYER == "BoundaryConditions"


# =============================================================================
# Which solvers produce displacements
# =============================================================================


@pytest.fixture(scope="module")
def results_show():
    return load_command(command_path("Results_show"), "results_show")


@pytest.mark.parametrize(
    "key, expected",
    [
        ("RBE_BC1", "RBE"),
        ("CRA_BC1-BC2", "CRA"),
        ("LMGC90_BC1", "LMGC90"),
        ("", ""),
    ],
)
def test_solver_of_reads_the_result_key(results_show, key, expected):
    assert results_show.solver_of(key) == expected


def test_displaced_is_offered_only_for_a_displacement_solver(results_show):
    """CRA/RBE store an identity transformation per block, so Displaced would
    draw an exact copy of the model. The solver comes from the KEY, not from
    problem.solver, which may have been changed since the solve."""
    assert results_show.offers_displacement(["LMGC90_BC1"], {}, None) is True
    assert results_show.offers_displacement(["RBE_BC1"], {}, None) is False
    assert results_show.offers_displacement(["CRA_BC1"], {}, None) is False

    # one displacement result among force results is enough to offer the choice
    assert results_show.offers_displacement(["RBE_BC1", "LMGC90_BC2"], {}, None) is True


# =============================================================================
# Table formatting
# =============================================================================


@pytest.fixture(scope="module")
def material():
    return load_command(command_path("Model_material"), "model_material")


def test_float_cells_cannot_blow_a_column(material):
    """str() of a float runs to 18 characters (0.19999999999999998), which is
    wider than any column and shifted every cell after it out of line."""
    assert material.cell(0.19999999999999998) == "0.2"
    assert material.cell(None) == "-"
    assert material.cell(2400) == "2400"
    assert len(material.cell(1 / 3)) <= 6


def test_table_columns_are_sized_to_their_contents(material, capsys):
    material.print_table(
        ["material", "fck", "density"],
        [["CONCRETE_C20/25", "20", "2400"], ["B", "3", "1800"]],
    )
    lines = [line for line in capsys.readouterr().out.splitlines() if line]

    header, rule, first, second = lines
    assert set(rule) == {"-"}
    # every row is exactly as wide as the header, whatever the name lengths
    assert len(header) == len(rule) == len(first) == len(second)
    # the numeric columns line up
    assert first.index("2400") == second.index("1800")


# =============================================================================
# Boundary-condition grouping
# =============================================================================


@pytest.fixture
def problem():
    """A problem over a real (small) model.

    An empty `BlockModel()` used to be enough, because loads were constructed
    directly and registered with `problem.add`. The `Problem.add_*` methods
    validate the block index against the model — `_block(index)` raises "No block
    at index 1; the model has 0 blocks" — so the fixture needs geometry now.
    """
    pytest.importorskip("compas_dem")
    pytest.importorskip("compas_cgal")
    from compas_dem.models import BlockModel
    from compas_dem.problem import Problem
    from compas_dem.templates import ArchTemplate

    model = BlockModel.from_template(ArchTemplate(rise=3.0, span=10.0, thickness=0.5, depth=0.5, n=6))
    return Problem(model, name="ULS")


def test_a_group_is_the_compas_dem_container(problem):
    """The group is `BoundaryConditionGroup`, not a name the plugin reads off each
    condition. That replaced the name-as-group scheme, which only existed because
    a Problem used to hold one flat list."""
    from compas_masonry.boundaryconditions import group_names, loads_of

    live = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=1, force=[0, 0, -5000], boundary_condition=live)
    problem.add_point_load_at_centroid(block_index=3, force=[0, 0, -1000], boundary_condition=live)
    wind = problem.add_boundary_condition("Wind")
    problem.add_surface_load(block_index=4, face_index=1, load=[0, 0, -200], boundary_condition=wind)

    assert group_names(problem, "load") == ["Load_1", "Wind"]
    assert len(loads_of(live)) == 2
    assert len(loads_of(wind)) == 1


def test_grouping_survives_serialization(problem):
    """The group is part of `Problem.__data__`, so the layer tree survives a
    reopen. It used to ride in the Data envelope as each condition's `name`."""
    import compas

    from compas_masonry.boundaryconditions import group_names, loads_of

    live = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=1, force=[0, 0, -5000], boundary_condition=live)
    wind = problem.add_boundary_condition("Wind")
    problem.add_surface_load(block_index=4, face_index=1, load=[0, 0, -200], boundary_condition=wind)

    back = compas.json_loads(compas.json_dumps(problem))
    assert group_names(back, "load") == ["Load_1", "Wind"]
    assert [len(loads_of(g)) for g in back.boundary_conditions] == [1, 1]


def test_group_kind_reads_content_never_the_name(problem):
    """An emptied group must not change sides. Guessing the kind from the name
    stem sent a custom-named group ("Settlement") to the other command's picker
    the moment its last condition was removed."""
    from compas_masonry.boundaryconditions import group_kind, remove_condition

    settle = problem.add_boundary_condition("Settlement")
    problem.add_displacement(block_index=0, displacement=[0.01, None, None], boundary_condition=settle)
    assert group_kind(settle) == "displacement"

    remove_condition(settle, settle.displacements[0])
    assert group_kind(settle) is None  # empty: no kind at all, not a guess


def test_an_empty_group_is_offered_to_both_commands(problem):
    """A group with no kind belongs to neither picker exclusively — so it can be
    refilled from the command it was created in, and deleted from either."""
    from compas_masonry.boundaryconditions import group_names

    problem.add_boundary_condition("Settlement")
    assert group_names(problem, "load") == ["Settlement"]
    assert group_names(problem, "displacement") == ["Settlement"]


def test_next_group_name_counts_past_gaps(problem):
    """Deleting a middle group must not hand back a name that is already taken.

    Names are unique across the WHOLE problem — `add_boundary_condition` raises on
    a duplicate whatever the group holds — so the count spans both kinds.
    """
    from compas_masonry.boundaryconditions import next_group_name

    assert next_group_name(problem, "load") == "Load_1"
    problem.add_boundary_condition("Load_1")
    problem.add_boundary_condition("Load_3")
    assert next_group_name(problem, "load") == "Load_2"

    # displacements number independently of loads
    assert next_group_name(problem, "displacement") == "Displacement_1"


def test_new_group_is_created_not_looked_up(problem):
    """`ask_load` must leave `group` as the SELECTOR and put the typed name in
    `newgroup`.

    It used to write the name into `group` — a leftover from when a group was only
    ever a string — so `resolve_group` saw a name instead of the New marker, went
    looking for a group that had not been created yet, and refused every new group
    with "Load group [Load_1] is no longer on this problem."
    """
    loads = load_command(command_path("Problem_loads"), "loads")

    created = loads.resolve_group(problem, {"group": loads.NEW, "newgroup": "Load_1"})
    assert created is not None and created.name == "Load_1"

    # picking it next time reuses the same object, never a second group
    reused = loads.resolve_group(problem, {"group": "Load_1", "newgroup": "Load_2"})
    assert reused is created
    assert [g.name for g in problem.boundary_conditions] == ["Load_1"]

    # a name already taken (by either kind) is refused, not raised
    problem.add_boundary_condition("Settlement")
    assert loads.resolve_group(problem, {"group": loads.NEW, "newgroup": "Settlement"}) is None


def test_removal_goes_through_the_live_lists(problem):
    """compas_dem exposes no remove; the plugin mutates the list properties, which
    are the live lists. If they ever return a copy, removal must FAIL LOUDLY
    rather than appear to work."""
    from compas_masonry.boundaryconditions import remove_condition, remove_group

    group = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=1, force=[0, 0, -1], boundary_condition=group)
    bc = group.point_loads[0]

    assert group.point_loads is group._point_loads
    assert problem.boundary_conditions is problem._boundary_conditions

    assert remove_condition(group, bc) is True
    assert group.point_loads == []
    assert remove_condition(group, bc) is False  # already gone

    assert remove_group(problem, group) is True
    assert problem.boundary_conditions == []
