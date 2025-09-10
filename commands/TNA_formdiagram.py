#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.6

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino
import compas_rhino.conversions
import compas_rhino.objects
from compas.datastructures import Mesh
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tna.envelope import Envelope

# Would be better to differentiate between an analysis using a known typology,
# for which both form diagram and envelope can be auto-generated based on a few params,
# and an analysis of a "custom" structure,
# for which the user has to define form diagram and envelope explicitly.

# We should be able to do introspection to automate the user queries.

# Perhaps the location of the diagrams can be decoupled from the base params.
# This allows the diagram to be moved afterwards without having to redefine the parameters.


def get_location():
    option = rs.GetString("Location", strings=["Origin", "Coordinates", "Point"])
    if not option:
        return

    if option == "Origin":
        point = (0, 0)

    elif option == "Coordinates":
        x = rs.GetReal("X", 0.0, -1000.0, 1000.0)
        if x is None:
            return

        y = rs.GetReal("Y", 0.0, -1000.0, 1000.0)
        if y is None:
            return

        point = (x, y)

    elif option == "Point":
        point = rs.GetPoint("Point")
        if not point:
            return

    else:
        raise NotImplementedError

    return point[0], point[1]


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

    option = rs.GetString(message="FormDiagram", strings=["FromPattern", "FromLines", "FromRhinoMesh"])
    if not option:
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
        option = rs.GetString(message="From Pattern", strings=["Circular", "Cross", "Fan", "Ortho"])
        if not option:
            return

        # =============================================================================
        # From a circular pattern
        # =============================================================================

        if option == "Circular":
            center = get_location()
            if not center:
                return

            radius = rs.GetReal("Radius", number=1.0, minimum=0.0)
            if not radius:
                return

            rings = rs.GetInteger("Rings", 8, 4, 32)
            if not rings:
                return

            radials = rs.GetInteger("Radials", 24, 12, 64)
            if not radials:
                return

            oculus = rs.GetReal("Oculus", number=0.3, minimum=0.0)
            if not oculus:
                return

            formdiagram = FormDiagram.create_circular_radial(
                center=center,
                radius=radius,
                n_hoops=rings,
                n_parallels=radials,
                r_oculus=oculus,
            )

        # =============================================================================
        # From a cross vault pattern
        # =============================================================================

        elif option == "Cross":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            n = rs.GetInteger("Resolution", 10, 0)
            if not n:
                return

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            formdiagram = FormDiagram.create_cross(
                x_span=x_span,
                y_span=y_span,
                n=n,
            )

        # =============================================================================
        # From a fan vault pattern
        # =============================================================================

        elif option == "Fan":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            n_fans = rs.GetInteger("Number of Fans", 10, 2)
            if not n_fans:
                return

            n_hoops = rs.GetInteger("Number of Hoops", n_fans, 2)
            if not n_hoops:
                return

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            formdiagram = FormDiagram.create_fan(
                x_span=x_span,
                y_span=y_span,
                n_fans=n_fans,
                n_hoops=n_hoops,
            )

        # =============================================================================
        # From an orthogonal pattern
        # =============================================================================

        elif option == "Ortho":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            nx = rs.GetInteger("Number of X Faces", 10, 2)
            if not nx:
                return

            ny = rs.GetInteger("Number of Y Faces", nx, 2)
            if not ny:
                return

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            formdiagram = FormDiagram.create_ortho(
                x_span=x_span,
                y_span=y_span,
                nx=nx,
                ny=ny,
            )

        # =============================================================================
        # Not supported
        # =============================================================================

        else:
            raise NotImplementedError

    # =============================================================================
    # Not supported
    # =============================================================================

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
    # Save
    # =============================================================================

    # if session.settings.autosave:
    #     session.record(name="FormDiagram")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
