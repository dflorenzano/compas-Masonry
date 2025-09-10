#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.6

import pathlib

import compas_rhino.objects
from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    guids = compas_rhino.objects.select_objects(message="Select supports")
    if not guids:
        return

    nodes = []
    for guid in guids:
        obj = compas_rhino.objects.find_object(guid)  # to make sure the object exists
        name = obj.Name
        if not name.startswith("Block"):
            continue

        node = int(name.split("_")[-1])
        nodes.append(node)

    supports = set(nodes)

    element: Block
    for node in model.graph.nodes():
        element = model.graph.node_element(node)  # type: ignore
        element.is_support = node in supports

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
