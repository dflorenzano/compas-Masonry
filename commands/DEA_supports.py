#! python3
# venv: brg-csd
# r: compas_masonry

import compas_rhino.objects
from compas.colors import Color
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session()

    model: BlockModel = session["blockmodel"]
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    guids = compas_rhino.objects.select_meshes(message="Select suports")
    if not guids:
        return

    nodes = []
    names = []
    for guid in guids:
        obj = compas_rhino.objects.find_object(guid)  # to make sure the object exists
        name = obj.Name
        if not name.startswith("Block"):
            continue

        node = int(name.split("_")[-1])
        nodes.append(node)
        names.append(name)

    for node in model.graph.nodes():
        model.graph.node_attribute(node, "is_support", node in nodes)

    for obj in session.scene.objects:
        if obj.name in names:
            obj.color = Color.red()

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
