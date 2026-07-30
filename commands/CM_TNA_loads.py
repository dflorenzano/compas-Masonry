#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_loads_options — RhinoCommon variant of TNA_loads.

Action, load type and the type-specific value are one prompt: picking
Selfweight shows the Normalize toggle, picking External shows the load
magnitude, picking ClearAll hides both. Vertex selection for external loads
still follows the accepted options.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.inputs import Options
from compas_masonry.scene import RhinoFormDiagramObject
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tna.envelope import Envelope


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    formdiagram: FormDiagram = session.get("formdiagram")

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

    options = Options("Loads")
    options.add_list("action", ["Add", "ClearAll"], keyword="Action")
    options.add_list("kind", ["Selfweight", "External", "FillLoads"], keyword="LoadType", visible=lambda v: v["action"] == "Add")
    options.add_toggle(
        "normalize",
        True,
        off="No",
        on="Yes",
        keyword="Normalize",
        prompt="Normalize loads to Envelope SWT",
        visible=lambda v: v["action"] == "Add" and v["kind"] == "Selfweight",
    )
    options.add_number(
        "load",
        -1.0,
        minimum=-1000.0,
        maximum=0.0,
        keyword="Magnitude",
        prompt="Load magnitude",
        visible=lambda v: v["action"] == "Add" and v["kind"] == "External",
    )

    values = options.get()
    if values is None:
        return

    if values["action"] == "Add":
        kind = values["kind"]

        if kind == "Selfweight":
            envelope.apply_selfweight_to_formdiagram(formdiagram, normalize=values["normalize"])  # type: ignore

        elif kind == "External":
            formobject.show_vertices = list(formobject.vertices())  # type: ignore
            formobject.show_edges = list(formobject.edges())  # type: ignore
            formobject.redraw()

            selected = formobject.select_vertices()
            if selected:
                load = values["load"]
                for key in selected:
                    pz = formdiagram.vertex_attribute(key, "pz") or 0
                    print("Load at vertex {0} updated from {1:.2f} to {2:.2f}".format(key, pz, pz + load))
                    formdiagram.vertex_attribute(key, "pz", pz + load)

        elif kind == "FillLoads":
            if not envelope.fill:
                feedback.warn("There is no Fill Mesh. Please re-create envelope with a fill")
                return
            envelope.apply_fill_weight_to_formdiagram(formdiagram)

    elif values["action"] == "ClearAll":
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
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
