#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.6

import pathlib

from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    if not confirm("Clear the current session?"):
        return

    session["params"] = {}

    session.delete("envelope")
    session.delete("formdiagram")
    session.delete("analysis")
    session.delete("blockmodel")

    session.scene.clear()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
