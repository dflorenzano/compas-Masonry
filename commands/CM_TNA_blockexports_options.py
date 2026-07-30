#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_blockexports_options — RhinoCommon variant of TNA_blockexports.

Generation mode and thickness bounds are one prompt; the tessellation pattern
(dozens of entries) stays a list dialog, and is only asked when Pattern is
picked. tmax >= tmin is checked after accepting, since the bound depends on
another option.

Semantics are unchanged: see TNA_blockexports.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore
from compas_libigl.mapping import TESSAGON_TYPES

from compas.datastructures import Mesh
from compas_dem.models import BlockModel
from compas_masonry.inputs import Options
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    # =============================================================================
    # Preconditions
    # =============================================================================

    formdiagram = session.get("formdiagram")
    if formdiagram is None:
        return warn("There is no FormDiagram in the session. Run the TNA workflow first.")

    thrust: Mesh = formdiagram.copy(cls=Mesh)

    zmax = max(abs(thrust.vertex_attribute(vertex, "z")) for vertex in thrust.vertices())
    if zmax < 1e-6:
        return warn("The form diagram is flat. Run TNA_analysis first to compute the thrust geometry.")

    # =============================================================================
    # Ask for input
    # =============================================================================

    options = Options("Block generation")
    options.add_list("option", ["Dual", "Pattern"], keyword="Blocks")
    options.add_number("tmin", 0.05, minimum=0.0, keyword="MinThickness", prompt="Minimum block thickness")
    options.add_number("tmax", 0.3, minimum=0.0, keyword="MaxThickness", prompt="Maximum block thickness")

    values = options.get()
    if values is None:
        return

    tmin = values["tmin"]
    tmax = values["tmax"]
    option = values["option"]

    if tmax < tmin:
        return warn(f"Maximum block thickness ({tmax}) is smaller than the minimum ({tmin}).")

    patternname = None
    if option == "Pattern":
        patternname = rs.ListBox(sorted(TESSAGON_TYPES), message="Tessellation pattern", title="Block pattern")
        if not patternname:
            return

    # =============================================================================
    # Generate the block model
    # =============================================================================

    try:
        if option == "Dual":
            model = BlockModel.from_triangulation_dual(thrust, tmin=tmin, tmax=tmax)
        else:
            model = BlockModel.from_meshpattern(thrust, patternname, tmin=tmin, tmax=tmax)
    except Exception as e:  # remeshing/mapping can fail on degenerate input
        return warn(f"Block generation failed: {e}")

    n_blocks = len(list(model.elements()))
    if not n_blocks:
        return warn("Block generation produced no blocks. Try a different pattern or thickness bounds.")

    # =============================================================================
    # Update session and scene
    # =============================================================================

    session.set_model(model)
    rs.Redraw()

    kind = f"{option}: {patternname}" if patternname else option
    print(f"BlockModel created from thrust diagram: {n_blocks} blocks ({kind}).")
    print("Next: Model_contacts to compute the contact interfaces.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
