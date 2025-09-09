#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.4

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.scene import RhinoFormDiagramObject
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    formdiagram: FormDiagram = session.get("formdiagram")

    if not formdiagram:
        feedback.warn("There is no FormDiagram. Please create one first.")
        return

    formobject: RhinoFormDiagramObject = session.scene.find_by_itemtype(FormDiagram)  # type: ignore
    if not formobject:
        session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore

    formobject.redraw()

    # =============================================================================
    # Update the supports
    # =============================================================================

    rs.UnselectAllObjects()

    option = rs.GetString("Add or Remove supports", strings=["Add", "Remove", "Clear All"])
    if not option:
        return

    if option == "Add":
        formobject.show_vertices = list(formobject.vertices())  # type: ignore
        formobject.show_edges = list(formobject.edges())  # type: ignore
        formobject.redraw()

        selected = formobject.select_vertices()

        if selected:
            formobject.mesh.vertices_attribute(name="is_support", value=True, keys=selected)

    elif option == "Remove":
        formobject.show_vertices = list(formobject.vertices())  # type: ignore
        formobject.show_edges = list(formobject.edges())  # type: ignore
        formobject.redraw()

        selected = formobject.select_vertices()

        if selected:
            formobject.mesh.vertices_attribute(name="is_support", value=False, keys=selected)

    elif option == "Clear All":
        formobject.mesh.vertices_attribute(name="is_support", value=False)

    else:
        raise NotImplementedError

    # =============================================================================
    # Update scene
    # =============================================================================

    rs.UnselectAllObjects()

    formobject.show_vertices = True  # type: ignore
    formobject.show_edges = True  # type: ignore
    formobject.show_faces = False  # type: ignore
    formobject.redraw()

    rs.Redraw()

    # =============================================================================
    # Save
    # =============================================================================

    # if session.settings.autosave:
    #     session.record(name="Analysis")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
