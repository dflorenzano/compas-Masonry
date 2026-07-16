#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_export — export the Problem to JSON (compas.json_dump)

STUB: not implemented yet. See temp/commands_list.md (Problem Group) for the
implementation notes and the compas_dem 0.5.0 API to call.
"""

import pathlib

from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")  # noqa: F841

    warn("Problem_export: not implemented yet.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
