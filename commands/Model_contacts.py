#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.layers
from compas_dem.interactions import FrictionContact
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_model.models import InteractionGraph
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        warn("No block model in the session.")
        return

    for obj in session.scene.find_all_by_itemtype(FrictionContact):
        session.scene.remove(obj)

    for obj in session.scene.find_all_by_itemtype(InteractionGraph):
        session.scene.remove(obj)

    compas_rhino.layers.clear_layer("Masonry::Model::Interactions")
    compas_rhino.layers.clear_layer("Masonry::Model::Contacts")

    # this should be simplified in the future
    # by adding a method model.clear_interactions()
    for u, v in list(model.graph.edges()):
        a = model.graph.node_element(u)  # type: ignore
        b = model.graph.node_element(v)  # type: ignore
        model.remove_interaction(a, b)

    session.scene.redraw()
    rs.Redraw()

    # =============================================================================
    # Ask for input
    # =============================================================================

    tolerance = rs.GetReal("Contact tolerance", session.settings.blockmodel.contact_tolerance, 1e-6)
    if tolerance is None:
        return

    minimum_area = rs.GetReal("Minimum contact area", session.settings.blockmodel.contact_minimum_area, 1e-6)
    if minimum_area is None:
        return

    # =============================================================================
    # Compute contacts
    # =============================================================================

    model.compute_contacts(tolerance=tolerance, minimum_area=minimum_area)

    # =============================================================================
    # Update scene
    # =============================================================================

    session.scene.add(model.graph, layer="Masonry::Model::Interactions")  # type: ignore

    for contact in model.contacts():
        session.scene.add(contact, layer="Masonry::Model::Contacts")  # type: ignore

    session.scene.redraw()

    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
