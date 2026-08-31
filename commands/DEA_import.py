#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas
import compas_rhino.layers
from compas_dem.elements import Block
from compas_dem.interactions import FrictionContact
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_model.models import InteractionGraph
from compas_rui import feedback
from compas_rui.forms import FileForm


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    path = rs.DocumentPath()  # to make sure the document has a path
    if path:
        basedir = pathlib.Path(path).parent
    else:
        basedir = pathlib.Path().home()

    filepath = FileForm.open(str(basedir))
    if not filepath:
        return

    try:
        result = compas.json_load(filepath)
    except Exception as e:
        feedback.warn(f"Failed to load datafrom {filepath}: {e}")
        return

    if not isinstance(result, BlockModel):
        feedback.warn(f"The data in the file is not a BlockModel: {type(result)}")
        return

    # =============================================================================
    # Clear existing model
    # =============================================================================

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

    # =============================================================================
    # Add new model
    # =============================================================================

    model: BlockModel = result
    session["blockmodel"] = model

    # =============================================================================
    # Update scene
    # =============================================================================

    # this should be simplifed by adding a helper method to the session

    for block in model.elements():
        node = block.graphnode
        session.scene.add(
            block,  # type: ignore
            name=f"Block_{node}",  # type: ignore
            group=f"Masonry::DEA::Blocks::{node}",  # type: ignore
            layer="Masonry::DEA::Blocks",  # type: ignore
        )

    if model.graph.number_of_edges() > 0:
        session.scene.add(model.graph, layer="Masonry::DEA::Interactions")  # type: ignore

        for contact in model.contacts():
            session.scene.add(contact, layer="Masonry::DEA::Contacts")  # type: ignore

    session.scene.redraw()

    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
