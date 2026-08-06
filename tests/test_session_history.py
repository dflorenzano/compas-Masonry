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

from compas_dem.problem import PointLoad  # noqa: E402
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
    """A session holding a model and one problem carrying one load."""
    problem = Problem(arch_model, name="Problem_1")
    problem.add(PointLoad.at_centroid(block=0, force=[0, 0, -1000]))

    session["blockmodel"] = arch_model
    session["problems"] = {"Problem_1": problem}
    session["active_problem"] = "Problem_1"
    return session


# =============================================================================
# The trap
# =============================================================================


def test_setdefault_does_not_read_from_disk(populated):
    """`session.problems` on an empty cache CLOBBERS the file. Pinned deliberately.

    `LazyLoadSession.setdefault` is:

        if key not in self.data:
            self.set(key, factory())

    `set()` autosyncs, so reading the `problems` property while `_data` is empty
    writes an empty dict straight over `data/problems.json`. That is why
    `_restore_data` primes every key with `get()` — the only accessor that falls
    through to the file — before anything touches a property.

    If this test ever fails, upstream fixed `setdefault` and the priming loop in
    `_restore_data` can be reconsidered (it stays harmless either way).
    """
    populated.record("with a problem")
    assert populated.problems  # sanity: it is there

    populated._data.clear()
    clobbered = populated.problems  # the property, NOT get()

    assert clobbered == {}
    # read the FILE, not the cache — the point is that the restored file is gone
    assert compas.json_load(populated.datadir / "problems.json") == {}


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
    populated["problems"] = {**populated.problems, "Problem_2": second}
    populated.record("two problems")

    assert sorted(populated.problems) == ["Problem_1", "Problem_2"]

    assert LazyLoadSession.undo(populated) is True
    populated._restore_data()

    assert list(populated.problems) == ["Problem_1"]


def test_restore_data_rebinds_problems_to_the_model(populated):
    """A reloaded Problem is UNBOUND — `problem.model` raises until rebound.

    This is the one live-object pointer in the plugin's stored state; everything
    else links by guid or by name and survives JSON on its own.
    """
    populated.record("one problem")
    populated._restore_data()

    problem = populated.problems["Problem_1"]
    assert problem.model is not None
    assert str(problem.model.guid) == problem.model_guid


def test_reloaded_problem_is_unbound_without_the_rebind(populated):
    """Pins WHY the rebind exists, by showing the failure it prevents."""
    populated.record("one problem")

    populated._data.clear()
    problem = populated.get("problems")["Problem_1"]

    with pytest.raises(ValueError):
        problem.model


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
    assert compas.json_load(snapshot / "blockmodel.json") is not None
    assert list(compas.json_load(snapshot / "problems.json")) == ["Problem_1"]


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
