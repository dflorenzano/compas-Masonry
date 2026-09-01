"""The command registry must match `commands/` exactly.

Registration lives in two files and drifts silently: a `rhproj` entry whose
`uri` no longer exists just fails to build, and a toolbar item naming a command
that does not exist produces a button that does nothing — the RUI loads fine
either way. Both had happened by 2026-07-30 (five dead entries, and every
toolbar item still using pre-`CM_` names), and neither showed up until someone
pressed a button.
"""

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "commands"
RHPROJ = ROOT / "COMPAS-Masonry.rhproj"
UI = ROOT / "resources" / "rui" / "ui.json"


@pytest.fixture(scope="module")
def command_files():
    return {path.stem for path in COMMANDS.glob("CM_*.py")}


@pytest.fixture(scope="module")
def rhproj():
    return json.loads(RHPROJ.read_text())


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI.read_text())


def test_rhproj_entries_match_the_command_files(rhproj, command_files):
    titles = {code["title"] for code in rhproj["codes"]}
    assert titles == command_files


def test_every_rhproj_uri_exists(rhproj):
    missing = [code["uri"] for code in rhproj["codes"] if not (ROOT / code["uri"]).exists()]
    assert missing == []


def test_rhproj_ids_are_unique(rhproj):
    ids = [code["id"] for code in rhproj["codes"]]
    assert len(ids) == len(set(ids))


def test_rhproj_titles_and_uris_agree(rhproj):
    """A renamed entry that kept its old uri would build the wrong script."""
    mismatched = [code["title"] for code in rhproj["codes"] if code["uri"] != f"commands/{code['title']}.py"]
    assert mismatched == []


def test_ui_commands_match_the_command_files(ui, command_files):
    names = {command["name"] for command in ui["commands"]}
    assert names == command_files


def test_ui_macros_match_their_command(ui):
    wrong = [c["name"] for c in ui["commands"] if c["script"] != f"! _{c['name']}"]
    assert wrong == []


def test_every_toolbar_item_is_a_registered_command(ui):
    """The failure this pins: items kept the pre-CM_ names and did nothing."""
    names = {command["name"] for command in ui["commands"]}
    items = {item["left"] for toolbar in ui["toolbars"] for item in toolbar["items"] if "left" in item}
    assert items - names == set()


def test_toolbar_items_match_commands(ui):
    """Every button is a real command, and only the parked set is off the bar.

    The TNA commands stay in commands/ and in ui.json — still typeable, still in
    the command palette — but were taken off the toolbar on 2026-08-28 pending a
    decision on retiring them. Pinning the set here means neither dropping a
    button by accident nor quietly parking another command passes unnoticed.
    """
    names = {command["name"] for command in ui["commands"]}
    items = {item["left"] for toolbar in ui["toolbars"] for item in toolbar["items"] if "left" in item}
    assert items - names == set()
    assert names - items == {
        "CM_TNA_analysis",
        "CM_TNA_blockexport",
        "CM_TNA_envelope",
        "CM_TNA_formdiagram",
        "CM_TNA_loads",
        "CM_TNA_supports",
    }


def test_toolbar_groups_reference_real_toolbars(ui):
    toolbars = {toolbar["name"] for toolbar in ui["toolbars"]}
    for group in ui["toolbargroups"]:
        assert set(group["toolbars"]) <= toolbars
