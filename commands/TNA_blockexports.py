#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_blockexports — export the TNA thrust diagram as a structurally informed BlockModel.

Bridge between the TNA and Model groups: takes the session's form diagram
(with the thrust geometry computed by TNA_analysis) and generates blocks
whose thickness follows the inverse of the thrust height, using either the
dual of a remeshed triangulation or a tessellation pattern (herringbone,
hex, brick, ...).

The resulting BlockModel replaces the session's current model (and any
dependent problem/results) via session.set_model().

Based on compas_dem/scripts/DEM_TNA_Mesh/.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore
from compas_libigl.mapping import TESSAGON_TYPES

from compas.datastructures import Mesh
from compas_dem.models import BlockModel
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

    option = rs.GetString(message="Block generation", strings=["Dual", "Pattern"])
    if not option:
        return

    patternname = None
    if option == "Pattern":
        patternname = rs.ListBox(sorted(TESSAGON_TYPES), message="Tessellation pattern", title="Block pattern")
        if not patternname:
            return

    tmin = rs.GetReal("Minimum block thickness", 0.05, 0.0)
    if tmin is None:
        return
    tmax = rs.GetReal("Maximum block thickness", 0.3, tmin)
    if tmax is None:
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
