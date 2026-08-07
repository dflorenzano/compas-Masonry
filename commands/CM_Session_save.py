#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Session_save — save the whole session to a single JSON file.

Saving and loading work the way RhinoVAULT's do: there is ONE thing to save and
ONE thing to open, the session. The per-artefact commands this replaced
(Model_export, Model_import, Problem_export) are gone — they wrote fragments
that could not be opened back into a working session on their own, and gave
three answers to "how do I save my work".

What is written: the `Analysis` — the model together with every problem and its
boundary conditions — plus the active problem name and the display settings.

The Analysis is what makes one key enough. A Problem serializes as a guid
REFERENCE to its model, so a file holding them separately has to hand the model
back to every problem on the way in; `Analysis.__from_data__` does that itself.

Solver results are NOT saved: they are solver specific and are re-derived by
Problem_solve. Per-block numbers come out of Results_block.

Re-open with Session_import. Files written before 2026-08-07 carried separate
`blockmodel` and `problems` keys and are NOT readable — Session_import says so
rather than importing half of one.
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
        "analysis": session.analysis,
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

    if session.model is None and not session.problems:
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

    analysis = data["analysis"]
    names = [problem.name for problem in analysis.problems]
    print(f"Exported session to {filepath}")
    print(f"  blockmodel: {'yes' if analysis.model is not None else 'no'}")
    print(f"  problems  : {len(names)} ({', '.join(names) or '-'})")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
