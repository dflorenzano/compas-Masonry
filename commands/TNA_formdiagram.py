#! python3
# venv: brg-csd
# r: compas_masonry

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.session import MasonrySession as Session
from compas_tna.diagrams import FormDiagram

# Would be better to differentiate between an analysis using a known typology,
# for which both form diagram and envelope can be auto-generated based on a few params,
# and an analysis of a "custom" structure,
# for which the user has to define form diagram and envelope explicitly.

# We should be able to do introspection to automate the user queries.

# Perhaps the location of the diagrams can be decoupled from the base params.
# This allows the diagram to be moved afterwards without having to redefine the parameters.


def RunCommand():
    session = Session()

    session.delete("formdiagram")

    for obj in session.scene.find_all_by_itemtype(FormDiagram):
        obj.clear()
        session.scene.remove(obj)

    # =============================================================================
    # Create a form diagram
    # =============================================================================

    formdiagram = None

    option = rs.GetString(message="FormDiagram", strings=["FromLines", "FromRhinoMesh", "FromPattern"])
    if not option:
        return

    if option == "FromLines":
        pass

    elif option == "FromRhinoMesh":
        pass

    elif option == "FromPattern":
        option = rs.GetString(message="From Pattern", strings=["Circular", "Cross", "Fan", "Ortho"])
        if not option:
            return

        # =============================================================================
        # From a circular pattern
        # =============================================================================

        if option == "Circular":
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
                center=(0, 0),
                radius=radius,
                n_hoops=rings,
                n_parallels=radials,
                r_oculus=oculus,
            )

            session["params"]["formdiagram"] = "circular"
            session["params"]["center"] = (0, 0)
            session["params"]["radius"] = radius
            session["params"]["n_hoops"] = rings
            session["params"]["n_parallels"] = radials
            session["params"]["r_oculus"] = oculus

        # =============================================================================
        # From a cross vault pattern
        # =============================================================================

        elif option == "Cross":
            xsize = rs.GetReal("XSize", number=10, minimum=0)
            if not xsize:
                return
            x_span = (0, xsize)

            ysize = rs.GetReal("YSize", number=xsize, minimum=0)
            if not ysize:
                return
            y_span = (0, ysize)

            n = rs.GetInteger("Resolution", 10, 2)
            if not n:
                return

            formdiagram = FormDiagram.create_cross(x_span=x_span, y_span=y_span, n=n)

            session["params"]["formdiagram"] = "cross"
            session["params"]["x_span"] = x_span
            session["params"]["y_span"] = y_span
            session["params"]["n"] = n

        # =============================================================================
        # From a fan vault pattern
        # =============================================================================

        elif option == "Fan":
            xsize = rs.GetReal("XSize", number=10, minimum=0)
            if not xsize:
                return
            x_span = (0, xsize)

            ysize = rs.GetReal("YSize", number=xsize, minimum=0)
            if not ysize:
                return
            y_span = (0, ysize)

            n_fans = rs.GetInteger("Number of Fans", 10, 2)
            if not n_fans:
                return

            n_hoops = rs.GetInteger("Number of Hoops", n_fans, 2)
            if not n_hoops:
                return

            formdiagram = FormDiagram.create_fan(x_span=x_span, y_span=y_span, n_fans=n_fans, n_hoops=n_hoops)

            session["params"]["formdiagram"] = "fan"
            session["params"]["x_span"] = x_span
            session["params"]["y_span"] = y_span
            session["params"]["n_fans"] = n_fans
            session["params"]["n_hoops"] = n_hoops

        # =============================================================================
        # From an orthogonal pattern
        # =============================================================================

        elif option == "Ortho":
            xsize = rs.GetReal("XSize", number=10, minimum=0)
            if not xsize:
                return
            x_span = (0, xsize)

            ysize = rs.GetReal("YSize", number=xsize, minimum=0)
            if not ysize:
                return
            y_span = (0, ysize)

            nx = rs.GetInteger("Number of X Faces", 10, 2)
            if not nx:
                return

            ny = rs.GetInteger("Number of Y Faces", nx, 2)
            if not ny:
                return

            formdiagram = FormDiagram.create_ortho(x_span=x_span, y_span=y_span, nx=nx, ny=ny)

            session["params"]["formdiagram"] = "ortho"
            session["params"]["x_span"] = x_span
            session["params"]["y_span"] = y_span
            session["params"]["nx"] = nx
            session["params"]["ny"] = ny

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
