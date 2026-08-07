"""Every command that changes session state must record it.

A command's body only runs inside Rhino, so a missing `session.record(...)` is
invisible to every headless test — and its symptom is not an error. The state
change simply never reaches a snapshot, the next undo replaces the working copy
with one that lacks it, and the change is gone with nothing reported.

That happened twice on 2026-08-06. `CM_Results_show` writes `shown_results`, the
only record of which results are drawn, and did not record — so the first undo
deleted it and the result geometry could never be redrawn. The failure looked
like a broken redraw, three layers away from the cause.

These are structural checks over the source text, not behavioural tests: they
cannot run the commands, but they can insist on the pairing.
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "commands"

# TNA is deliberately outside the history: its envelope and form diagram are drawn
# inline by those commands rather than through the session, so a restore has
# nothing to call. See temp/status_open_decisions.md §7.10.
EXCLUDED = {"CM_TNA_analysis.py", "CM_TNA_blockexport.py", "CM_TNA_envelope.py", "CM_TNA_formdiagram.py", "CM_TNA_loads.py", "CM_TNA_supports.py"}

# Session_clear empties everything and calls `clear_history()` instead: records
# pointing at a model the user has just deleted are worse than no records.
CLEARS_INSTEAD = {"CM_Session_clear.py"}


def session_keys() -> list:
    """`MasonrySession.SESSION_KEYS`, read statically so this needs no Rhino."""
    source = (ROOT / "src" / "compas_masonry" / "session.py").read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SESSION_KEYS" for t in node.targets):
            return [e.value for e in node.value.elts]
    raise AssertionError("SESSION_KEYS not found")


def commands_assigning_session_keys() -> list:
    """Command files containing `session["<a session key>"] = ...`."""
    keys = session_keys()
    found = []
    for path in sorted(COMMANDS.glob("CM_*.py")):
        if path.name in EXCLUDED:
            continue
        text = path.read_text()
        if any(f'session["{key}"] =' in text for key in keys):
            found.append(path)
    return found


@pytest.mark.parametrize("path", commands_assigning_session_keys(), ids=lambda p: p.name)
def test_command_writing_session_state_records_it(path):
    """Writing a session key without recording means it never reaches a snapshot."""
    text = path.read_text()
    if path.name in CLEARS_INSTEAD:
        assert "session.clear_history()" in text
        return
    assert "session.record(" in text, (
        f"{path.name} assigns a session key but never calls session.record(). "
        "The change will not reach a snapshot, and the next undo will discard it silently."
    )


@pytest.mark.parametrize("path", commands_assigning_session_keys(), ids=lambda p: p.name)
def test_recording_command_takes_a_baseline(path):
    """`undo()` refuses at `current == 0`, so the oldest record is a floor rather
    than a destination. Without a baseline taken BEFORE the first change, the
    first command of a session can never be undone."""
    text = path.read_text()
    if path.name in CLEARS_INSTEAD:
        return
    assert "session.ensure_baseline()" in text, f"{path.name} records but never calls session.ensure_baseline()."


def test_the_expected_commands_are_the_ones_recording():
    """Pins the set, so adding a state-changing command is a deliberate decision
    rather than something that silently opts out of history."""
    recording = {p.name for p in sorted(COMMANDS.glob("CM_*.py")) if p.name not in EXCLUDED and "session.record(" in p.read_text()}

    assert recording == {
        "CM_Model_blocks.py",
        "CM_Model_contacts.py",
        "CM_Model_material.py",
        "CM_Model_materialassign.py",
        "CM_Model_supports.py",
        "CM_Problem_contactlaw.py",
        "CM_Problem_create.py",
        "CM_Problem_displacements.py",
        "CM_Problem_loads.py",
        "CM_Problem_setsolver.py",
        "CM_Problem_solve.py",
        "CM_Results_show.py",
        "CM_Session_import.py",
    }
