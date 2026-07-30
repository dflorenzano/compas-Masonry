#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_formdiagram_options — RhinoCommon variant of TNA_formdiagram.

Each pattern is defined in a single prompt, location included (Origin /
Coordinates / Point, with X and Y appearing only for Coordinates).

Semantics are unchanged: see TNA_formdiagram.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino
import compas_rhino.conversions
import compas_rhino.objects
from compas.datastructures import Mesh
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tna.envelope import Envelope


def add_location(options):
    """Add the location options (shared by every pattern)."""
    options.add_list("location", ["Origin", "Coordinates", "Point"], keyword="Location")
    options.add_number("x", 0.0, minimum=-1000.0, maximum=1000.0, keyword="X", visible=lambda v: v["location"] == "Coordinates")
    options.add_number("y", 0.0, minimum=-1000.0, maximum=1000.0, keyword="Y", visible=lambda v: v["location"] == "Coordinates")
    return options


def resolve_location(values):
    """Turn the accepted location options into an (x, y) tuple, or None if cancelled."""
    if values["location"] == "Origin":
        return 0.0, 0.0
    if values["location"] == "Coordinates":
        return values["x"], values["y"]
    point = rs.GetPoint("Point")
    if not point:
        return None
    return point[0], point[1]


def get_circular():
    options = add_location(Options("Circular pattern"))
    options.add_number("radius", 1.0, minimum=0.0, keyword="Radius")
    options.add_integer("rings", 8, minimum=4, maximum=32, keyword="Rings")
    options.add_integer("radials", 24, minimum=12, maximum=64, keyword="Radials")
    options.add_number("oculus", 0.3, minimum=0.0, keyword="Oculus")

    values = options.get()
    if values is None:
        return None
    center = resolve_location(values)
    if center is None:
        return None

    return FormDiagram.create_circular_radial(
        center=center,
        radius=values["radius"],
        n_hoops=values["rings"],
        n_parallels=values["radials"],
        r_oculus=values["oculus"],
    )


def get_cross():
    options = add_location(Options("Cross pattern"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_integer("n", 10, minimum=1, keyword="Resolution")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return FormDiagram.create_cross(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        n=values["n"],
    )


def get_fan():
    options = add_location(Options("Fan pattern"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_integer("n_fans", 10, minimum=2, keyword="Fans")
    options.add_integer("n_hoops", 10, minimum=2, keyword="Hoops")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return FormDiagram.create_fan(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        n_fans=values["n_fans"],
        n_hoops=values["n_hoops"],
    )


def get_ortho():
    options = add_location(Options("Ortho pattern"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_integer("nx", 10, minimum=2, keyword="XFaces")
    options.add_integer("ny", 10, minimum=2, keyword="YFaces")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return FormDiagram.create_ortho(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        nx=values["nx"],
        ny=values["ny"],
    )


PATTERNS = {
    "Circular": get_circular,
    "Cross": get_cross,
    "Fan": get_fan,
    "Ortho": get_ortho,
}


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    # =============================================================================
    # Remove existing form diagram
    # =============================================================================

    session.delete("formdiagram")

    for obj in session.scene.find_all_by_itemtype(FormDiagram):
        obj.clear()
        session.scene.remove(obj)

    # =============================================================================
    # Check for existing envelope
    # =============================================================================

    envelope: Envelope = session.get("envelope")
    if not envelope:
        feedback.warn("There is no Envelope. Please create one first.")
        return

    # =============================================================================
    # Create a (new) form diagram
    # =============================================================================

    formdiagram = None
    rs.UnselectAllObjects()

    option = choose("FormDiagram", ["FromPattern", "FromLines", "FromRhinoMesh"])
    if option is None:
        return

    # =============================================================================
    # From Rhino lines
    # =============================================================================

    if option == "FromLines":
        guids = compas_rhino.objects.select_lines("Select lines")
        if not guids:
            return

        lines = compas_rhino.objects.get_line_coordinates(guids)
        if not lines:
            return

        mesh_formdiagram = Mesh.from_lines(lines, delete_boundary_face=True)  # type: ignore
        formdiagram = FormDiagram.from_mesh(mesh_formdiagram)

        rs.HideObjects(guids)

    # =============================================================================
    # From a Rhino mesh
    # =============================================================================

    elif option == "FromRhinoMesh":
        guid = compas_rhino.objects.select_mesh("Select FormDiagram Mesh")
        rs.UnselectAllObjects()
        if not guid:
            return
        obj = compas_rhino.objects.find_object(guid)
        mesh_formdiagram = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)
        formdiagram = FormDiagram.from_mesh(mesh_formdiagram)

        rs.HideObjects(guid)

    # =============================================================================
    # From a predefined pattern
    # =============================================================================

    elif option == "FromPattern":
        pattern = choose("Pattern", list(PATTERNS.keys()))
        if pattern is None:
            return
        formdiagram = PATTERNS[pattern]()

    else:
        raise NotImplementedError

    # =============================================================================
    # Update scene
    # =============================================================================

    if not formdiagram:
        return

    session["formdiagram"] = formdiagram

    session.settings.formdiagram.show_reactions = False
    session.settings.formdiagram.show_pipes = False

    envelope.apply_bounds_to_formdiagram(formdiagram)

    session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore
    session.scene.redraw()

    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
