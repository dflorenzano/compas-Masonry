#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_loads — apply loads: gravity / point / surface (problem.add_gravity / add_point_load / add_surface_load)

STUB: not implemented yet. See temp/commands_list.md (Problem Group) for the
implementation notes and the compas_dem 0.5.0 API to call.
"""

# Sub menu which allows the use to choose whether to apply gravity, point or surface loads to the current problem.
# Problem loads -> Point Loads -> Magnitude and direction of the load -> Do you want to add more? ->

# Create Problem -> Name
# Loads -> Select Problem -> Add / Remove / Modify Loads -> Gravity / Point / Surface -> Magnitude and direction of the load -> Do you want to add more? ->
# if Add, create name for the load, and repeat the process of selecting the type of load and its magnitude and direction.
# if Remove, select the load to remove and confirm removal.
# if modify, select the load to modify and change its magnitude and direction.

# same goes for displacements

# then the

import pathlib

from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")  # noqa: F841

    warn("Problem_loads: not implemented yet.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
