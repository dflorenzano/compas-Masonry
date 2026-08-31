"""Headless tests: session history, and the restore half of undo/redo.

`MasonrySession.undo()` / `redo()` fill a slot `LazyLoadSession` left empty. The
parent moves FILES between `__records/<id>/` and the working copy and stops — it
never touches `_data` or `_scene`, and `get()` only reads from disk when a key is
missing from `_data`, so without the override an undo changes nothing observable.
See `temp/wiki_session_primer.md` §7 and §8.4.

What is pinned here is `_restore_data()`, which is deliberately the half that
needs no Rhino: it is also the only half that can silently destroy a user's work
(see `test_setdefault_does_not_read_from_disk`). `_redraw_state()` needs a live
document and is not covered — the drawing it does is `draw_model()` and
`draw_problem_conditions()`, both already exercised by Session_import.
"""

import json

import compas
import pytest

pytest.importorskip("compas_dem")
pytest.importorskip("compas_cgal")  # BlockModel hard-imports it

from compas_dem.models import Analysis  # noqa: E402
from compas_dem.problem import Problem  # noqa: E402
from compas_masonry.session import MasonrySession  # noqa: E402


@pytest.fixture
def session(tmp_path):
    """A session rooted in tmp_path.

    The class is a singleton keyed on `cls._instance`, so it MUST be released
    between tests — otherwise the second test silently reuses the first one's
    basedir and its history.

    The scene is passed in with an explicit context rather than letting
    `LazyLoadSession` build one. A default `Scene()` calls
    `detect_current_context()`, which reaches for `scriptcontext.doc` — and once
    any other test module has installed `rhinostub`, `scriptcontext` exists in
    `sys.modules` without a `doc`, so these tests pass alone and error out in a
    full run. Nothing here draws, so the context value only has to be stable.
    """
    from compas.scene import Scene

    MasonrySession.delete_instance()
    instance = MasonrySession(basedir=tmp_path, name="test", scene=Scene(context="Rhino"))
    yield instance
    MasonrySession.delete_instance()


@pytest.fixture
def populated(session, arch_model):
    """A session holding a model and one problem carrying one load.

    Model and problems travel together in ONE key now: `Analysis`. The two-key
    form this used to build (`blockmodel` + `problems`) is what made a reloaded
    problem come back unbound.
    """
    problem = Problem(arch_model, name="Problem_1")
    group = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=0, force=[0, 0, -1000], boundary_condition=group)

    analysis = Analysis(model=arch_model, name="test")
    analysis.add_problem(problem)

    session["analysis"] = analysis
    session["active_problem"] = "Problem_1"
    return session


# =============================================================================
# The trap
# =============================================================================


def test_setdefault_still_clobbers_a_cold_cache(populated):
    """`setdefault` on an empty cache DESTROYS the file. Pinned deliberately.

    `LazyLoadSession.setdefault` is:

        if key not in self.data:
            self.set(key, factory())

    `set()` autosyncs, so calling it while `_data` is empty writes an empty
    container straight over the file on disk. Shown here on `results`, which
    Problem_solve reaches through `session.setdefault("results", dict)`.

    This is why `_restore_data` primes every key with `get()` — the only accessor
    that falls through to the file — before anything else runs.

    If this test ever fails, upstream fixed `setdefault` and the priming loop can
    be reconsidered (it stays harmless either way).
    """
    populated["results"] = {"Problem_1": {"CRA_x": "placeholder"}}
    populated.record("with results")

    populated._data.clear()
    clobbered = populated.setdefault("results", dict)

    assert clobbered == {}
    # read the STORAGE, not the cache — the point is that the data on disk is gone.
    # `results` is a folder now, so "empty" is a manifest naming nothing.
    assert compas.json_load(populated.resultsdir / "_results.json") == []
    assert populated._load_results() == {}


def test_the_analysis_property_reads_through_to_disk(populated):
    """The one key that must never be reachable by `setdefault`.

    `analysis` holds the model AND every problem, so clobbering it destroys the
    whole session in one call — where the old `problems` key cost only the
    problems. `MasonrySession.analysis` therefore goes through `get()` and only
    creates an empty Analysis when the disk really has nothing.
    """
    populated.record("with a problem")

    populated._data.clear()
    analysis = populated.analysis  # the property, on a COLD cache

    assert analysis.model is not None
    assert [problem.name for problem in analysis.problems] == ["Problem_1"]


def test_restore_data_primes_before_touching_properties(populated):
    """The guard against the above: a restore must not lose the problems."""
    populated.record("with a problem")

    populated._restore_data()

    assert list(populated.problems) == ["Problem_1"]


# =============================================================================
# Restoring
# =============================================================================


def test_restore_data_brings_back_the_previous_state(populated, arch_model):
    """record -> mutate -> record -> undo -> the first state is back.

    `LazyLoadSession.undo` is called directly rather than
    `MasonrySession.undo`, because the override also calls `_redraw_state`,
    which needs a live Rhino document.
    """
    from compas_session.lazyload import LazyLoadSession

    populated.record("one problem")

    second = Problem(arch_model, name="Problem_2")
    populated.add_problem(second)
    populated.record("two problems")

    assert sorted(populated.problems) == ["Problem_1", "Problem_2"]

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()

    assert list(populated.problems) == ["Problem_1"]


def test_restore_binds_problems_to_the_model_with_no_rebind_step(populated):
    """A reloaded Problem is UNBOUND on its own — `problem.model` raises. The
    Analysis is what hands the model back, inside `__from_data__`.

    `_restore_data` used to end with an explicit loop calling `_bind_model` on
    every problem. That loop is gone, and this pins that nothing needs to replace
    it: the binding falls out of storing one object instead of two.
    """
    populated.record("one problem")
    populated._restore_data()

    problem = populated.problems["Problem_1"]
    assert problem.model is not None
    assert str(problem.model.guid) == problem.model_id
    # the same object, not a second copy deserialized alongside it
    assert problem.model is populated.model


def test_a_problem_stored_on_its_own_would_come_back_unbound(populated):
    """Pins WHY the analysis holds both, by showing what storing a problem alone
    does: it serializes a guid reference and returns unbound, so every load path
    would need its own rebinding step (and one that forgot would fail at solve
    time, not at load time)."""
    problem = populated.problems["Problem_1"]

    alone = compas.json_loads(compas.json_dumps(problem))

    with pytest.raises(ValueError):
        alone.model


def test_restore_data_survives_an_empty_session(session):
    """No model, no problems, no settings file — a restore must not raise."""
    session.record("empty")
    session._restore_data()

    assert session.get("blockmodel") is None
    assert session.problems == {}


# =============================================================================
# Guards
# =============================================================================


def test_undo_refuses_with_no_history(session):
    """Returns False before `_restore_state`, so it is safe to call headless."""
    assert session.undo() is False


def test_undo_refuses_at_the_oldest_record(populated):
    """`current == 0` is a floor, not a destination — which is why a baseline
    has to be recorded before the first real change (`ensure_baseline`)."""
    populated.record("only state")

    assert populated.undo() is False


def test_redo_refuses_at_the_newest_record(populated):
    populated.record("only state")

    assert populated.redo() is False


def test_ensure_baseline_records_once(session):
    session.ensure_baseline()
    assert len(session.history) == 1

    session.ensure_baseline()
    assert len(session.history) == 1


def test_ensure_baseline_makes_the_first_action_undoable(populated):
    """Without a baseline the first command of a session can never be undone.

    The parent's `undo` is called directly: `MasonrySession.undo` would go on to
    `_redraw_state`, which needs a live document. The False-returning cases above
    are safe to call on the override, because it returns before reaching it.
    """
    from compas_session.lazyload import LazyLoadSession

    populated.ensure_baseline()
    populated["active_problem"] = "Problem_1"
    populated.record("first action")

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()


# =============================================================================
# Depth
# =============================================================================


def test_history_survives_a_session_rebuilt_between_commands(tmp_path):
    """The case that matters in Rhino, and the one a same-process test misses.

    Every command is a fresh `Session(...)`, and `__init__` calls `load_history()`.
    `LazyLoadSession.record` writes `_history.json` BEFORE updating `_current`, so
    the persisted cursor is one behind — and reloading it makes the next `record()`
    discard the forward branch against a cursor stuck at 0. Symptom: history never
    exceeds two entries and undo always answers "Nothing more to undo!".

    `MasonrySession.record` re-dumps the history to close it.
    """
    from compas.scene import Scene

    def open_session():
        """What a command does when it constructs the session."""
        MasonrySession.delete_instance()
        return MasonrySession(basedir=tmp_path, name="test", scene=Scene(context="Rhino"))

    session = open_session()
    session.ensure_baseline()
    session["active_problem"] = "a"
    session.record("one")

    session = open_session()
    session["active_problem"] = "b"
    session.record("two")

    session = open_session()
    session["active_problem"] = "c"
    session.record("three")

    session = open_session()
    assert [name for _, name in session.history] == ["Initial state", "one", "two", "three"]
    assert session.current == 3

    from compas_session.lazyload import LazyLoadSession

    assert LazyLoadSession.undo(session) is True
    session._restore_data()
    assert session.get("active_problem") == "b"

    MasonrySession.delete_instance()


def test_history_is_capped_at_depth(session):
    """Every record is a full COPY of the data directory, so the cap is what
    keeps a session folder from growing without bound."""
    assert session.depth == 10

    for i in range(12):
        session["active_problem"] = f"state_{i}"
        session.record(f"state {i}")

    assert len(session.history) == 10
    assert session.history[-1][1] == "state 11"


def test_dropped_records_do_not_leak_their_folders(session):
    """The depth trim drops LIST entries with a slice assignment and never deletes
    the folders — and `clear_history` cannot reach them afterwards, because it
    iterates the list. Past `_depth` that orphans one full copy of the session per
    command, without bound. `MasonrySession.record` sweeps them.
    """
    for i in range(15):
        session["active_problem"] = f"state_{i}"
        session.record(f"state {i}")

    folders = [p for p in session.recordsdir.iterdir() if p.is_dir()]
    assert len(folders) == len(session.history) == 10

    # every surviving folder is one the history still points at
    assert {p.name for p in folders} == {record for record, _ in session.history}


def test_discarded_forward_branch_does_not_leak_its_folders(populated):
    """The other place the parent shortens the list: record after an undo."""
    from compas_session.lazyload import LazyLoadSession

    for i in range(4):
        populated["active_problem"] = f"state_{i}"
        populated.record(f"state {i}")

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()

    populated["active_problem"] = "branched"
    populated.record("new branch")  # discards everything ahead of the cursor

    folders = {p.name for p in populated.recordsdir.iterdir() if p.is_dir()}
    assert folders == {record for record, _ in populated.history}


def test_record_snapshots_the_autosynced_working_copy(populated):
    """`record` empties `_data` around the parent call to skip a redundant
    re-serialization (0.45s per command on a 6.5 MB model, for byte-identical
    files). The snapshot must still hold the real data — it comes from the
    autosynced working copy rather than from the dump.
    """
    populated["active_problem"] = "Problem_1"
    populated.record("with data")

    record_id, _ = populated.history[-1]
    snapshot = populated.recordsdir / record_id / populated.datadirname

    assert compas.json_load(snapshot / "active_problem.json") == "Problem_1"

    # ONE key, stored as a FOLDER: the model and the problems are separate files
    # under `analysis/`, and there is no monolithic analysis.json (nor the
    # blockmodel.json / problems.json that predated it).
    assert not (snapshot / "analysis.json").exists()

    manifest = compas.json_load(snapshot / "analysis" / "_analysis.json")
    assert manifest["problems"] == ["Problem_1.json"]
    assert compas.json_load(snapshot / "analysis" / "model.json") is not None
    assert compas.json_load(snapshot / "analysis" / "problems" / "Problem_1.json").name == "Problem_1"


def test_record_still_dumps_scene_and_settings(session):
    """Those four do NOT come from `_data`, so emptying the cache must not stop
    them being written into the snapshot."""
    session.record("state")

    record_id, _ = session.history[-1]
    folder = session.recordsdir / record_id

    for filename in (session.scenefilename, session.settingsfilename, session.tolerancefilename, session.versionfilename):
        assert (folder / filename).exists(), filename


def test_snapshot_scene_is_a_fresh_one_on_purpose(populated):
    """Pinned so it reads as a decision rather than a bug.

    `_scene.json` has no reader — the `scene` property only loads it when
    `_scene` is falsy, and an empty Scene is truthy — and the restore rebuilds the
    scene from the data (§8.4). Writing the real one costs an object-graph walk
    over every block, at twice the bytes of the model, on every command.

    The live scene cannot be populated headlessly (no Rhino scene object is
    registered for a Block outside Rhino), so the scene's own `name` — which
    `Scene.__data__` serializes — stands in as the marker.

    The file must still be PRESENT: `undo()` copies it out of the record folder
    unconditionally and would raise FileNotFoundError otherwise.
    """
    populated.scene.name = "LIVE"
    populated.record("with a marked scene")

    record_id, _ = populated.history[-1]
    snapshot = populated.recordsdir / record_id / populated.scenefilename

    assert snapshot.exists()

    # the raw JSON, not `compas.json_load`: reconstructing a Scene calls
    # `Scene.__from_data__` -> `cls(data["name"])` with no context, which detects
    # one by reaching for `scriptcontext.doc`. Reading the file is also the
    # stronger assertion — it is the file that gets copied around, not an object.
    written = json.loads(snapshot.read_text())["data"]

    assert written["name"] != "LIVE"  # a fresh scene was written
    assert written["items"] == []
    assert written["root"].get("children", []) == []

    assert populated.scene.name == "LIVE"  # the live scene is handed back untouched


def test_shown_results_is_dropped_with_the_results(populated):
    """The record of what is on screen cannot outlive the results it names.

    `clear_results` deletes both, so `Model_contacts` invalidating the results
    cannot leave a replay pointing at result keys that no longer exist.
    """
    populated["results"] = {"Problem_1": {"RBE_x": None}}
    populated["shown_results"] = {"Problem_1": {"keys": ["RBE_x"], "mode": "Forces"}}

    # only the session bookkeeping is exercised; the layer sweep needs Rhino
    populated.delete("results")
    populated.delete("shown_results")

    assert populated.get("results") is None
    assert populated.get("shown_results") is None
    assert "shown_results" in populated.SESSION_KEYS  # so clear_all sweeps it too


def test_shown_results_is_restored_by_undo(populated):
    """It is a session key, so a snapshot carries it and a restore brings it back —
    which is what lets `draw_shown_results` rebuild the view."""
    from compas_session.lazyload import LazyLoadSession

    populated["shown_results"] = {"Problem_1": {"keys": ["RBE_a"], "mode": "Both"}}
    populated.record("results shown")

    populated["shown_results"] = {}
    populated.record("results hidden")

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()

    assert populated.get("shown_results") == {"Problem_1": {"keys": ["RBE_a"], "mode": "Both"}}


def test_draw_shown_results_skips_keys_that_no_longer_exist(populated):
    """Undoing to before a solve SHOULD take its geometry with it. The key naming
    it can survive, because it records intent rather than data — so the replay has
    to tolerate it rather than raise."""
    populated["results"] = {}
    populated["shown_results"] = {"Problem_1": {"keys": ["RBE_gone"], "mode": "Forces"}}

    assert populated.draw_shown_results(model=None) == 0


def test_scene_property_never_loads_the_file(session):
    """The assumption the decision above rests on.

    If an empty `Scene` were ever falsy, `session.scene` would fall through to
    `compas.json_load(self.scenefile)` and quietly produce the copied-item scene
    §8.4 exists to avoid.
    """
    from compas.scene import Scene

    assert bool(Scene(context="Rhino")) is True
    assert session._scene is not None


# =============================================================================
# Which end of a boundary-condition arrow sits on the point of application
# =============================================================================


def test_load_arrow_head_lands_on_the_point_of_application():
    """A force PUSHES into the geometry: the head is at the anchor, not away
    from it. `rs.CurveArrows(guid, 2)` heads the END, so "tip" must put the
    anchor there and walk the start back along the vector."""
    start, end = MasonrySession._arrow_endpoints([0.0, 0.0, 10.0], [0.0, 0.0, -2.0], "tip")
    assert end == [0.0, 0.0, 10.0]  # the anchor
    assert start == [0.0, 0.0, 12.0]  # upstream, so a downward force points down


def test_tail_arrows_still_start_at_the_point():
    """Body force and prescribed movement keep the old convention."""
    start, end = MasonrySession._arrow_endpoints([0.0, 0.0, 10.0], [0.0, 0.0, -2.0], "tail")
    assert start == [0.0, 0.0, 10.0]
    assert end == [0.0, 0.0, 8.0]


def test_a_zero_vector_gives_a_degenerate_arrow_either_way():
    """`_draw_bc_vector` bails on start == end; both modes must agree on that."""
    for at in ("tip", "tail"):
        start, end = MasonrySession._arrow_endpoints([1.0, 2.0, 3.0], [0.0, 0.0, 0.0], at)
        assert start == end


# =============================================================================
# session.summary()
# =============================================================================


def test_summary_on_an_empty_session(session):
    """Must report empty rather than raise: `summary` is the first thing anyone
    runs when they are lost, which is exactly when the session may be blank."""
    text = session.summary()
    assert "no block model" in text
    assert "problems : none" in text
    assert "results  : none" in text


def test_summary_reports_problems_and_history(session, arch_model):
    """`set_model` needs Rhino, so the analysis is populated directly — the
    summary must read through the accessors, not through a draw."""
    session["analysis"] = Analysis(model=arch_model, name="test")
    problem = Problem(model=arch_model, name="Problem_1")
    session.add_problem(problem)
    session.record("added a problem")

    text = session.summary()
    assert "Problem_1" in text
    assert "no boundary conditions" in text
    assert "1 record(s)" in text
    assert "added a problem" in text


def test_summary_reports_contact_properties(session, arch_model):
    """Status includes the mechanical assumptions attached to each problem."""
    session["analysis"] = Analysis(model=arch_model, name="test")
    problem = Problem(model=arch_model, name="Problem_1")
    problem.set_contact_model("MohrCoulomb", phi=35.0, c=1000.0, t_c=0.0)
    problem.set_joint_model(100e9, 70e9)
    session.add_problem(problem)

    text = session.summary()

    assert "contact law: MohrCoulomb" in text
    assert "phi 35.0 deg" in text
    assert "cohesion 1000.0 Pa" in text
    assert "joint model: kn 100000000000.0 Pa | kt 70000000000.0 Pa" in text


# =============================================================================
# BlockModel settings actually reach the drawing code
# =============================================================================


def test_every_show_setting_is_read_somewhere():
    """Item 7's regression guard.

    12 of 21 BlockModelSettings fields were read by NOTHING — the dialog offered
    them and the drawing ignored them. A field that does nothing is worse than no
    field, so this fails if one is added back without a consumer.
    """
    import pathlib

    from compas_masonry.settings import BlockModelSettings

    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "compas_masonry"
    code = "\n".join(p.read_text() for p in src.rglob("*.py") if p.name != "settings.py")
    commands = pathlib.Path(__file__).resolve().parents[1] / "commands"
    code += "\n".join(p.read_text() for p in commands.glob("*.py"))

    unread = []
    for name in BlockModelSettings.model_fields:
        # pickmode_* are reached with getattr(settings, f"pickmode_{what}")
        if name.startswith("pickmode_") and "pickmode_" in code:
            continue
        if name not in code:
            unread.append(name)

    assert unread == [], f"BlockModel settings read by nothing: {unread}"


# =============================================================================
# User Text tagging
# =============================================================================


def _tagged(params):
    """Run `set_user_params` against a recording stub, returning what it wrote.

    `set_user_params` never touches `self`, so it is called unbound rather than
    standing a whole session up around a Rhino document it would not have.
    """
    import sys

    import rhinostub

    rhinostub.install()
    written = {}
    sys.modules["rhinoscriptsyntax"].SetUserText = lambda guid, key, value: written.__setitem__(key, value)

    MasonrySession.set_user_params(object(), "guid", params)
    return written


def test_compas_geometry_is_tagged_as_a_plain_list():
    """A face-anchored point load used to abort the whole redraw.

    compas_dem resolves the two point-load anchors differently:
    `add_point_load_at_vertex` uses `vertex_coordinates()` -> list, while
    `add_point_load_at_face` uses `face_center()` -> Point. Tagging the Point
    raised `TypeError: Object of type Point is not JSON serializable` inside
    `draw_problem_conditions`, which tags as it draws — so the loads before it got
    arrows, the ones after got none, and the load looked like it had only applied
    to one block. It had always been added and saved; only the drawing died.
    """
    from compas.geometry import Point
    from compas.geometry import Vector

    written = _tagged({"point": Point(1.0, 2.0, 3.0), "force": Vector(0.0, 0.0, -1000.0)})

    assert json.loads(written["point"]) == [1.0, 2.0, 3.0]
    assert json.loads(written["force"]) == [0.0, 0.0, -1000.0]


def test_plain_values_are_tagged_unchanged():
    """The list-returning anchor must still produce exactly what it always did."""
    written = _tagged({"point": [1.0, 2.0, 3.0], "loading_type": "ramp", "face_index": 4, "moment": None})

    assert json.loads(written["point"]) == [1.0, 2.0, 3.0]
    assert written["loading_type"] == "ramp"  # strings stay raw, not quoted JSON
    assert json.loads(written["face_index"]) == 4
    assert written["moment"] is None  # None deletes the key


def test_an_unencodable_value_still_raises():
    """`default=list` must not become a silent catch-all for anything at all."""
    with pytest.raises(TypeError):
        _tagged({"nonsense": object()})


# =============================================================================
# Folder-backed storage for `analysis` and `results`
# =============================================================================


def _problem(model, name):
    problem = Problem(model, name=name)
    group = problem.add_boundary_condition("Load_1")
    problem.add_point_load_at_centroid(block_index=0, force=[0, 0, -1000], boundary_condition=group)
    return problem


def test_the_analysis_round_trips_through_separate_files(session, arch_model):
    """The whole point: the model and each problem are their own JSON, and the
    Analysis that comes back is bound exactly as `__from_data__` leaves it."""
    analysis = Analysis(model=arch_model, name="test")
    analysis.add_problem(_problem(arch_model, "Problem_1"))
    analysis.add_problem(_problem(arch_model, "Problem_2"))
    session["analysis"] = analysis

    session._data.clear()
    back = session.get("analysis")

    assert back.name == "test"
    assert [problem.name for problem in back.problems] == ["Problem_1", "Problem_2"]
    assert [group.name for group in back.problems[0].boundary_conditions] == ["Load_1"]
    # the reason this stayed ONE key: nothing had to rebind by hand
    assert all(problem.model is back.model for problem in back.problems)


def test_the_analysis_is_stored_as_a_folder_not_a_file(populated):
    assert not (populated.datadir / "analysis.json").exists()
    assert (populated.analysisdir / "model.json").exists()
    assert (populated.problemsdir / "Problem_1.json").exists()
    assert compas.json_load(populated.analysisdir / "_analysis.json")["problems"] == ["Problem_1.json"]


def test_removed_problems_do_not_come_back(session, arch_model):
    """A state with fewer problems than the last one must not leave files behind
    for the next load to find — that would resurrect a deleted problem."""
    analysis = Analysis(model=arch_model, name="test")
    for name in ("Problem_1", "Problem_2", "Problem_3"):
        analysis.add_problem(_problem(arch_model, name))
    session["analysis"] = analysis

    analysis.problems = analysis.problems[:1]
    session["analysis"] = analysis

    session._data.clear()
    assert [problem.name for problem in session.get("analysis").problems] == ["Problem_1"]
    assert sorted(p.name for p in session.problemsdir.iterdir()) == ["Problem_1.json"]


def test_a_legacy_monolith_is_still_read(session, arch_model):
    """Pre-folder sessions, and every undo record taken before the folder existed,
    hold one `analysis.json`. It must load, and the next write must replace it."""
    analysis = Analysis(model=arch_model, name="legacy")
    analysis.add_problem(_problem(arch_model, "Problem_1"))

    import shutil

    compas.json_dump(analysis, session.datadir / "analysis.json")
    shutil.rmtree(session.analysisdir, ignore_errors=True)
    session._data.clear()

    back = session.get("analysis")
    assert back.name == "legacy"
    assert [problem.name for problem in back.problems] == ["Problem_1"]
    assert back.problems[0].model is back.model

    session["analysis"] = back
    assert not (session.datadir / "analysis.json").exists()
    assert (session.analysisdir / "_analysis.json").exists()


def test_the_two_keys_share_a_directory_without_sharing_a_lifetime(populated):
    """`CM_TNA_envelope` deletes the analysis and keeps the results, so deleting
    one key must not take the other's files with it."""
    populated["results"] = {"Problem_1": {"CRA_1": "placeholder"}}

    populated.delete("analysis")
    populated._data.clear()
    assert populated.get("analysis") is None
    assert populated.get("results") == {"Problem_1": {"CRA_1": "placeholder"}}

    populated["analysis"] = Analysis(model=None, name="test")
    populated.delete("results")
    populated._data.clear()
    assert populated.get("results") is None
    assert populated.get("analysis") is not None


def test_the_narrow_writes_touch_only_their_own_half(populated):
    """The whole reason for the split.

    `save_model` must not re-serialize the problems, and — the one that pays —
    `save_problems` must not re-serialize the MODEL. On a 200-block arch the model
    is 0.50 MB against 878 bytes for a problem, 0.031s against 0.0001s to write.
    `save_analysis` is the both-changed case and writes everything.
    """
    modelfile = populated.analysisdir / "model.json"
    problemfile = populated.problemsdir / "Problem_1.json"

    model_before, problem_before = modelfile.stat().st_mtime_ns, problemfile.stat().st_mtime_ns
    populated.save_model()
    assert modelfile.stat().st_mtime_ns != model_before
    assert problemfile.stat().st_mtime_ns == problem_before

    model_before, problem_before = modelfile.stat().st_mtime_ns, problemfile.stat().st_mtime_ns
    populated.save_problems()
    assert modelfile.stat().st_mtime_ns == model_before
    assert problemfile.stat().st_mtime_ns != problem_before

    model_before = modelfile.stat().st_mtime_ns
    populated.save_analysis()
    assert modelfile.stat().st_mtime_ns != model_before


def test_every_problem_editing_command_uses_the_narrow_write(populated):
    """A problem edit that calls `save_analysis` silently pays the model write.

    Pinned as source inspection because the alternative is standing up each command
    against a Rhino document. Model_* commands are the mirror image and must NOT
    appear here.
    """
    import pathlib

    commands = pathlib.Path(__file__).resolve().parents[1] / "commands"
    offenders = sorted(p.name for p in commands.glob("CM_Problem_*.py") if "save_analysis()" in p.read_text())

    assert offenders == [], f"problem commands rewriting the model for nothing: {offenders}"


def test_a_narrow_write_cannot_be_the_first_write(session, arch_model):
    """`save_model` on a session that still holds a legacy monolith must write the
    WHOLE folder. A bare model.json would leave the manifest missing, the load path
    would fall back to the legacy file, and the saved model would be read back
    stale — silently."""
    analysis = Analysis(model=arch_model, name="legacy")
    analysis.add_problem(_problem(arch_model, "Problem_1"))

    import shutil

    compas.json_dump(analysis, session.datadir / "analysis.json")
    shutil.rmtree(session.analysisdir, ignore_errors=True)
    session._data.clear()

    session.get("analysis")  # warms the cache from the legacy file
    session.save_model()

    assert (session.analysisdir / "_analysis.json").exists()
    assert not (session.datadir / "analysis.json").exists()

    session._data.clear()
    assert [problem.name for problem in session.get("analysis").problems] == ["Problem_1"]


def test_undo_across_the_format_change(populated, arch_model):
    """A record taken BEFORE the folder existed is restored as a legacy monolith.
    This is the case that would silently lose a model.

    `LazyLoadSession.undo` rather than the override, as everywhere else here: the
    override also runs `_redraw_state`, which needs a live Rhino document.
    """
    import shutil

    from compas_session.lazyload import LazyLoadSession

    populated.record("folder state")

    # forge a pre-folder record: the snapshot holds analysis.json and no folder
    record_id, _ = populated.history[-1]
    snapshot = populated.recordsdir / record_id / populated.datadirname
    legacy = Analysis(model=arch_model, name="from-a-legacy-record")
    legacy.add_problem(_problem(arch_model, "Problem_9"))
    shutil.rmtree(snapshot / "analysis", ignore_errors=True)
    compas.json_dump(legacy, snapshot / "analysis.json")

    populated["active_problem"] = "moved on"
    populated.record("after")

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()

    back = populated.get("analysis")
    assert back.name == "from-a-legacy-record"
    assert [problem.name for problem in back.problems] == ["Problem_9"]
    assert back.problems[0].model is back.model


# =============================================================================
# Result force layers
#
# One layer per drawn quantity. Everything except the value tags used to land on
# a single "Forces" layer, which is why corner forces were never seen in Rhino:
# the data is written on every FrictionContact, but the lines were drawn
# underneath the resultants on the same layer, with no way to switch either off.
# =============================================================================


def test_every_force_view_has_its_own_layer():
    """No two drawn quantities may share a sublayer, or one hides the other."""
    paths = list(MasonrySession.RESULT_FORCE_LAYERS.values())

    assert len(paths) == len(set(paths))
    assert all(path.startswith("Forces::") for path in paths)


def test_the_force_layer_tree_matches_the_agreed_grouping():
    """Pins the shape, so a regrouping is a decision rather than a drift.

    Normal and friction hang off Reactions (the interface force in the joint's
    own frame); horizontal and vertical hang off Resultants (the same force in
    world axes). X/Y/Z are the world-axis parts of a support reaction and are
    kept off the Interface layer — they share its colour, so on one layer neither
    could be switched off without the other.
    """
    assert MasonrySession.RESULT_FORCE_LAYERS == {
        "resultants": "Forces::Resultants",
        "horizontal": "Forces::Resultants::Horizontal",
        "vertical": "Forces::Resultants::Vertical",
        "reactions": "Forces::Reactions::Interface",
        "normal": "Forces::Reactions::Normal",
        "friction": "Forces::Reactions::Friction",
        "reaction_x": "Forces::Reactions::X",
        "reaction_y": "Forces::Reactions::Y",
        "reaction_z": "Forces::Reactions::Z",
        "corners": "Forces::Corners",
        "values": "Forces::Values",
    }


class _ArrowRecorder:
    """Stands in for the session so the component maths can be read back.

    `_draw_reaction_components` only needs `_draw_vector_arrow` and the reaction
    colour, so an unbound call with this in place of `self` exercises the real
    method without Rhino.
    """

    COLOR_REACTION = (214, 40, 40)

    def __init__(self):
        self.calls = []

    def _draw_vector_arrow(self, layer, point, vector, color=None, params=None):
        self.calls.append({"layer": layer, "point": tuple(point), "vector": tuple(vector), "params": params})
        return "guid"


_LAYERS = {"reaction_x": "…::X", "reaction_y": "…::Y", "reaction_z": "…::Z"}


def test_reaction_components_sum_back_to_the_reaction():
    """Three parts of one force, not three forces — so they must add up."""
    recorder = _ArrowRecorder()
    reaction = [-10.881, 4.0, 25.852]
    scale = 2.0

    drawn = MasonrySession._draw_reaction_components(recorder, _LAYERS, [1.0, 2.0, 3.0], reaction, scale)

    assert drawn == 3
    total = [sum(call["vector"][axis] for call in recorder.calls) for axis in range(3)]
    assert total == pytest.approx([c * scale for c in reaction])


def test_reaction_components_share_the_resultant_point_and_split_by_layer():
    recorder = _ArrowRecorder()

    MasonrySession._draw_reaction_components(recorder, _LAYERS, [1.0, 2.0, 3.0], [1.0, 1.0, 1.0], 1.0)

    assert {call["point"] for call in recorder.calls} == {(1.0, 2.0, 3.0)}
    assert [call["layer"] for call in recorder.calls] == ["…::X", "…::Y", "…::Z"]
    assert [call["params"]["component_axis"] for call in recorder.calls] == ["x", "y", "z"]


def test_a_zero_component_draws_nothing():
    """The reference arch is planar: Ry is 0, and a zero-length arrow is noise."""
    recorder = _ArrowRecorder()

    drawn = MasonrySession._draw_reaction_components(recorder, _LAYERS, [0.0, 0.0, 0.0], [-10.881, 0.0, 25.852], 1.0)

    assert drawn == 2
    assert [call["params"]["component_axis"] for call in recorder.calls] == ["x", "z"]


def test_a_numerically_zero_component_draws_nothing_either():
    """A planar arch solves to Ry = 6e-07 N, not to 0.

    An `== 0` test would let that through and add a ~1e-11 m arrow to the
    document: invisible, unselectable and unexplainable. The threshold is
    relative to the reaction, so it scales with the model rather than assuming
    newtons and metres.
    """
    recorder = _ArrowRecorder()

    drawn = MasonrySession._draw_reaction_components(recorder, _LAYERS, [0.0, 0.0, 0.0], [-10.881, 6.0656e-07, 25.852], 1.0)

    assert drawn == 2
    assert [call["params"]["component_axis"] for call in recorder.calls] == ["x", "z"]


# =============================================================================
# BUG 1 — the force-scale yardstick must not depend on placement
# =============================================================================


class _FakeGeometry:
    def __init__(self, points):
        self._points = points

    def vertices_attributes(self, _):
        return list(self._points)


class _SizedBlock:
    def __init__(self, points):
        self.modelgeometry = _FakeGeometry(points)


class _SizedModel:
    def __init__(self, blocks):
        self._blocks = blocks

    def elements(self):
        return iter(self._blocks)


def _unit_cube():
    return [(x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]


def test_the_yardstick_is_the_block_diameter():
    """A unit cube's diameter is its space diagonal, sqrt(3)."""
    model = _SizedModel([_SizedBlock(_unit_cube())])

    assert MasonrySession._max_block_size(None, model) == pytest.approx(3**0.5)


def test_rotating_a_model_does_not_rescale_its_force_arrows():
    """BUG 1. The axis-aligned bbox diagonal drifted 23% over a 45 degree turn.

    Same cube, turned about a skew axis: the block is unchanged, so the yardstick
    it sets must be unchanged too, or every arrow in the document silently
    rescales when someone rotates the model.
    """
    import math

    upright = _SizedModel([_SizedBlock(_unit_cube())])

    def turned(angle):
        c, s = math.cos(angle), math.sin(angle)
        points = []
        for x, y, z in _unit_cube():
            # rotate about Z, then about X — enough to move every axis
            x1, y1 = x * c - y * s, x * s + y * c
            y2, z2 = y1 * c - z * s, y1 * s + z * c
            points.append((x1, y2, z2))
        return _SizedModel([_SizedBlock(points)])

    reference = MasonrySession._max_block_size(None, upright)
    for degrees in (15, 30, 45, 60):
        rotated = MasonrySession._max_block_size(None, turned(math.radians(degrees)))
        assert rotated == pytest.approx(reference), f"yardstick moved at {degrees} degrees"


def test_an_empty_model_still_gives_a_usable_yardstick():
    """Zero would make the scale a division by zero at the call site."""
    assert MasonrySession._max_block_size(None, _SizedModel([])) == 1.0
