#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_rui import feedback
from compas_session.lazyload import LazyLoadSession as Session


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    # reaction forces
    #


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
