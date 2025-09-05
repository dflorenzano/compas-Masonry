#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.session import MasonrySession as Session


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
