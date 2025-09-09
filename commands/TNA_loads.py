#! python3
# venv: brg-csd
# r: compas_masonry >=0.2.0

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.scene import RhinoFormDiagramObject
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tna.envelope import Envelope


def RunCommand():
    session = Session()

    formdiagram: FormDiagram = session["formdiagram"]

    if not formdiagram:
        feedback.warn("There is no FormDiagram. Please create one first.")
        return

    formobject: RhinoFormDiagramObject = session.scene.find_by_itemtype(FormDiagram)  # type: ignore
    if not formobject:
        session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore

    envelope: Envelope = session["envelope"]
    if not envelope:
        feedback.warn("There is no Envelope. Please create one first.")
        return

    # =============================================================================
    # Update the Loads
    # =============================================================================

    rs.UnselectAllObjects()

    options = ["Add", "ClearAll"]
    option = rs.GetString("Add or Remove Loads in the Model", strings=options)
    if not option:
        return

    if option == "Add":
        option = rs.GetString("Type of load", strings=["Selfweight", "External"])
        if not option:
            return

        if option == "Selfweight":
            option = rs.GetString("Normalize loads to Envelope SWT?", defaultString="Yes", strings=["Yes", "No"])
            if not option:
                return
            elif option == "Yes":
                normalize = True
            else:
                normalize = False
            envelope.apply_selfweight_to_formdiagram(formdiagram, normalize=normalize)

        elif option == "External":
            formobject.show_vertices = list(formobject.vertices())  # type: ignore
            formobject.show_edges = list(formobject.edges())  # type: ignore
            formobject.redraw()

            selected = formobject.select_vertices()
            if selected:
                load = rs.GetReal("Load magnitude", -1.0, -1000.0, 0.0)
                if load is None:
                    return

                for key in selected:
                    pz = formdiagram.vertex_attribute(key, "pz") or 0
                    print("Load at vertex {0} updated from {1:.2f} to {2:.2f}".format(key, pz, pz + load))
                    formdiagram.vertex_attribute(key, "pz", pz + load)

    elif option == "ClearAll":
        print("Cleared Loads in the Model.")
        formobject.mesh.vertices_attribute(name="pz", value=0)

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
