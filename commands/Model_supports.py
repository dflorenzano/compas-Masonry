#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Model_supports — mark blocks as supports (Add / Remove / Clear).

Supports are model-level: setting Block.is_support drives both the Rhino layer
(Masonry::Model::Supports) and the colour (red), and is inherited by every
Problem via add_supports_from_model.

The command only sets is_support flags, then lets the scene redraw derive the
layer + colour from those flags (session.sync_support_layers + session.redraw).
It never moves layers with captured guids — Scene.redraw() recreates every
Rhino object with new guids, so a captured guid would be dead after a redraw
(the "does not exist in ObjectTable" error). Selection guids are resolved to
graph nodes via the persistent "element_guid" tag before any redraw.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    option = rs.GetString(message="Select an option", strings=["Add", "Remove", "Clear"])
    if not option:
        return

    guid_element_map = session.guid_element_map(model)

    if option in ("Add", "Remove"):
        verb = "add" if option == "Add" else "remove"
        guids = compas_rhino.objects.select_objects(message=f"Select supports you want to {verb}")
        if not guids:
            return
        nodes = {n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None}
        if not nodes:
            return warn("No blocks resolved from the selection.")
        for node in nodes:
            model.graph.node_element(node).is_support = option == "Add"
        print(f"{option}: {len(nodes)} support(s).")

    elif option == "Clear":
        for node in model.graph.nodes():
            model.graph.node_element(node).is_support = False
        print("Cleared all supports.")

    # Persist, route scene objects to the right layer per is_support, redraw once.
    # The redraw recreates objects with the correct layer + red colour, and
    # re-tags element_guid / material_guid / is_support.
    session["blockmodel"] = model
    session.sync_support_layers()
    session.redraw()


if __name__ == "__main__":
    RunCommand()
