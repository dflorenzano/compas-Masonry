#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Masonry_export_options — export the whole session to a single JSON file.

Model_export writes only the BlockModel and Problem_export only one problem.
This writes the session: the model, every problem with its boundary conditions, the
active problem, and the display settings — so a session can be handed over or
archived in one file, and re-opened with Masonry_import.

Everything stored is a compas Data (BlockModel, Problem), so compas.json_dump
serializes it directly. Solver results are NOT exported: they are solver
specific and are re-derived by Problem_solve.
"""

import pathlib

import compas
import rhinoscriptsyntax as rs  # type: ignore
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn
from compas_rui.forms import FileForm


def session_data(session) -> dict:
    """Collect the exportable session state."""
    data = {
        "blockmodel": session.get("blockmodel"),
        "problems": dict(session.problems),
        "active_problem": session.active_problem_name,
    }

    # settings are pydantic, not compas Data
    try:
        data["settings"] = session.settings.model_dump()
    except Exception as e:
        print(f"Settings not exported ({e}).")

    return data


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    if session.get("blockmodel") is None and not session.problems:
        return warn("Nothing to export: the session has no BlockModel and no problem.")

    path = rs.DocumentPath()  # to make sure the document has a path
    basedir = pathlib.Path(path).parent if path else pathlib.Path().home()

    filepath = FileForm.save(str(basedir), "Masonry_session.json")
    if not filepath:
        return

    data = session_data(session)

    try:
        compas.json_dump(data, filepath)
    except Exception as e:
        return warn(f"Export failed: {e}")

    print(f"Exported session to {filepath}")
    print(f"  blockmodel: {'yes' if data['blockmodel'] is not None else 'no'}")
    print(f"  problems  : {len(data['problems'])} ({', '.join(data['problems']) or '-'})")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
