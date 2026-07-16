#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.layers
from compas_dem.elements import Block
from compas_dem.interactions import FrictionContact
from compas_dem.models import BlockModel
from compas_dem.templates import ArchTemplate
from compas_dem.templates import BarrelVaultTemplate
from compas_dem.templates import DomeTemplate
from compas_masonry.session import MasonrySession as Session
from compas_model.models import InteractionGraph

# =============================================================================
# Command
# =============================================================================


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    session.delete("blockmodel")

    for obj in session.scene.find_all_by_itemtype(Block):
        session.scene.remove(obj)

    for obj in session.scene.find_all_by_itemtype(FrictionContact):
        session.scene.remove(obj)

    for obj in session.scene.find_all_by_itemtype(InteractionGraph):
        session.scene.remove(obj)

    compas_rhino.layers.clear_layer("Masonry::DEA::Blocks")
    compas_rhino.layers.clear_layer("Masonry::DEA::Interactions")
    compas_rhino.layers.clear_layer("Masonry::DEA::Contacts")

    model = None

    option = rs.GetString(message="BlockModel", strings=["Arch", "Dome", "BarrelVault", "Meshes", "Json"])
    if not option:
        return

    # =============================================================================
    # Arch
    # =============================================================================

    if option == "Arch":
        rise = rs.GetReal("Rise", 3.0, 0.0)
        if not rise:
            return
        span = rs.GetReal("Span", 10.0, 0.0)
        if not span:
            return
        thickness = rs.GetReal("Thickness", 0.5, 0.0)
        if not thickness:
            return
        depth = rs.GetReal("Depth", 0.5, 0.0)
        if not depth:
            return
        n = rs.GetInteger("Number of blocks", 50, 3)
        if not n:
            return

        template = ArchTemplate(rise=rise, span=span, thickness=thickness, depth=depth, n=n)
        model = BlockModel.from_template(template)

    # =============================================================================
    # Dome
    # =============================================================================

    elif option == "Dome":
        meridians = rs.GetInteger("Number of meridians", 40, 3)
        if not meridians:
            return
        hoops = rs.GetInteger("Number of hoops", 20, 3)
        if not hoops:
            return
        oculus = rs.GetReal("Oculus angle (rad)", 3.14 / 30, 0.0)
        if not oculus:
            return
        spring = rs.GetReal("Springing angle (rad)", 3.14 / 2, 0.0)
        if not spring:
            return
        r_i = rs.GetReal("Inner radius at springing", 3.9, 0.0)
        if not r_i:
            return
        r_f = rs.GetReal("Inner radius at oculus", 3.2, 0.0)
        if not r_f:
            return
        R_i = rs.GetReal("Outer radius at springing", 4.0, 0.0)
        if not R_i:
            return
        R_f = rs.GetReal("Outer radius at oculus", 3.5, 0.0)
        if not R_f:
            return

        template = DomeTemplate(meridians=meridians, hoops=hoops, oculus=oculus, spring=spring, r_i=r_i, r_f=r_f, R_i=R_i, R_f=R_f)
        model = BlockModel.from_template(template)

    # =============================================================================
    # BarrelVault
    # =============================================================================

    elif option == "BarrelVault":
        span = rs.GetReal("Span", 10.0, 0.0)
        if not span:
            return
        length = rs.GetReal("Length", 20.0, 0.0)
        if not length:
            return
        rise = rs.GetReal("Rise", 3.0, 0.0)
        if not rise:
            return
        thickness = rs.GetReal("Thickness", 0.5, 0.0)
        if not thickness:
            return
        n = rs.GetInteger("Number of span blocks", 50, 3)
        if not n:
            return
        m = rs.GetInteger("Number of length blocks", 20, 3)
        if not m:
            return

        template = BarrelVaultTemplate(span=span, length=length, rise=rise, thickness=thickness, vou_span=n, vou_length=m)
        model = BlockModel.from_barrelvault(template)

    # =============================================================================
    # Meshes
    # =============================================================================

    elif option == "Meshes":
        guids = rs.GetObjects("Select meshes", rs.filter.mesh)
        if not guids:
            return

        model = BlockModel.from_rhinomeshes(guids)

    # =============================================================================
    # Surface/Pattern
    # =============================================================================

    # =============================================================================
    # FormDiagram
    # =============================================================================

    # =============================================================================
    # Json
    # =============================================================================

    elif option == "Json":
        pass

    else:
        raise NotImplementedError

    # =============================================================================
    # Session update
    # =============================================================================

    if not model:
        return

    session["blockmodel"] = model

    # =============================================================================
    # Scene
    # =============================================================================

    for block in model.elements():
        node = block.graphnode
        session.scene.add(
            block,  # type: ignore
            name=f"Block_{node}",  # type: ignore
            group=f"Masonry::DEA::Blocks::{node}",  # type: ignore
            layer="Masonry::DEA::Blocks",  # type: ignore
        )

    session.scene.redraw()

    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
