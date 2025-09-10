#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.6

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn
from compas_rui.forms import FileForm


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    blockmodel = session.get("blockmodel")
    if not blockmodel:
        warn("No block model in the session.")
        return

    path = rs.DocumentPath()  # to make sure the document has a path
    if path:
        basedir = pathlib.Path(path).parent
    else:
        basedir = pathlib.Path().home()

    filepath = FileForm.save(str(basedir), "Masonry_DEM.json")
    if not filepath:
        return

    compas.json_dump(blockmodel, filepath)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
