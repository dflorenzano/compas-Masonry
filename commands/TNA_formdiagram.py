#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_session.lazyload import LazyLoadSession as Session
from compas_tna.diagrams import FormDiagram


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    session["params"] = {}

    session.scene.clear()
    session.delete("formdagram")

    # =============================================================================
    # Create a form diagram
    # =============================================================================

    formdiagram = None

    option = rs.GetString(message="FormDiagram", strings=["Circular", "Cross", "Fan", "Ortho"])
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

        session["params"]["formdiagram"] = "circular_radial"
        session["params"]["center"] = (0, 0)
        session["params"]["radius"] = radius
        session["params"]["n_hoops"] = rings
        session["params"]["n_parallels"] = radials
        session["params"]["r_oculus"] = oculus

    # =============================================================================
    # From a cross vault pattern
    # =============================================================================

    elif option == "Cross":
        x_span = (0, 10)
        y_span = (0, 10)
        n = 10

        formdiagram = FormDiagram.create_cross()

        session["params"]["formdiagram"] = "cross"
        session["params"]["x_span"] = x_span
        session["params"]["y_span"] = y_span
        session["params"]["n"] = n

    # =============================================================================
    # From a fan vault pattern
    # =============================================================================

    elif option == "Fan":
        x_span = (0, 10)
        y_span = (0, 10)
        n_fans = 10
        n_hoops = 10

        formdiagram = FormDiagram.create_fan()

        session["params"]["formdiagram"] = "cross"
        session["params"]["x_span"] = x_span
        session["params"]["y_span"] = y_span
        session["params"]["n_fans"] = n_fans
        session["params"]["n_hoops"] = n_hoops

    # =============================================================================
    # From an orthogonal pattern
    # =============================================================================

    elif option == "Ortho":
        x_span = (0, 10)
        y_span = (0, 10)
        nx = 10
        ny = 10

        formdiagram = FormDiagram.create_ortho()

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
