#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rhino.layers import create_layers_from_path
from compas_rhino.layers import find_objects_on_layer
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    path_blocks = "Masonry::Model::Blocks"
    path_supports = "Masonry::Model::Supports"

    create_layers_from_path(path_supports, separator="::")

    # =============================================================================
    # Sync existing supports to the support layer
    # =============================================================================

    guid_element_map = session.guid_element_map(model)

    node_guid_map = {}
    for guid in find_objects_on_layer(path_blocks) + find_objects_on_layer(path_supports):
        node = session.find_node(guid, guid_element_map)
        if node is not None:
            node_guid_map[node] = guid

    element: Block
    for node in model.graph.nodes():
        element = model.graph.node_element(node)  # type: ignore
        guid = node_guid_map.get(node)
        if guid:
            rs.ObjectLayer(guid, path_supports if element.is_support else path_blocks)

    rs.Redraw()

    # =============================================================================
    # Options
    # =============================================================================

    option = rs.GetString(message="Select an option", strings=["Add", "Remove", "Clear"])
    if not option:
        return

    # =============================================================================
    # Add supports
    # =============================================================================

    if option == "Add":
        guids = compas_rhino.objects.select_objects(message="Select supports you want to add")
        if not guids:
            return

        nodes = {n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None}

        for node in nodes:
            model.graph.node_element(node).is_support = True
            guid = node_guid_map.get(node)
            if guid:
                rs.ObjectLayer(guid, path_supports)

        rs.Redraw()

    elif option == "Remove":
        guids = compas_rhino.objects.select_objects(message="Select supports you want to remove")
        if not guids:
            return

        nodes = {n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None}

        for node in nodes:
            model.graph.node_element(node).is_support = False  # type: ignore
            guid = node_guid_map.get(node)
            if guid:
                rs.ObjectLayer(guid, path_blocks)

        rs.Redraw()

    elif option == "Clear":
        for node in model.graph.nodes():
            model.graph.node_element(node).is_support = False

        for guid in node_guid_map.values():
            rs.ObjectLayer(guid, path_blocks)

        rs.Redraw()


if __name__ == "__main__":
    RunCommand()
