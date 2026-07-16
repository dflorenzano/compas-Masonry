#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Solve — run the analysis: model.solve(problem) with the solver configured
by Problem_solver. Produces a Results object for the Results commands.

STUB: not implemented yet. See temp/commands_list.md (Results Group).
Start with Solver.CRA() (pure-Python backend); catch ImportError from missing
solver backends and warn with an install hint instead of a traceback.
"""

import pathlib

from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")  # noqa: F841

    warn("Solve: not implemented yet.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
