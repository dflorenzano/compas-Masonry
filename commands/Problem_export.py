#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_export — export a Problem to JSON (compas.json_dump).

Problem is a compas.data.Data, so it serialises directly. Pick which problem to
export; the file carries the problem's model_id, so it can be validated against
a model on re-import.
"""

import pathlib

from compas_masonry.session import MasonrySession as Session

import compas
import rhinoscriptsyntax as rs  # type: ignore
from compas_rui.feedback import warn
from compas_rui.forms import FileForm


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to export")
    if name is None:
        return
    problem = session.problems[name]

    path = rs.DocumentPath()
    basedir = pathlib.Path(path).parent if path else pathlib.Path().home()

    filepath = FileForm.save(str(basedir), f"{name}.json")
    if not filepath:
        return

    compas.json_dump(problem, filepath)
    print(f"Exported {name} to {filepath}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
