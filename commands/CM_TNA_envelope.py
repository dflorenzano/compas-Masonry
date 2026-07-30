#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_envelope_options — RhinoCommon variant of TNA_envelope.

Each parametric envelope is defined in a single prompt: the location options
(Origin / Coordinates / Point, with X and Y appearing only for Coordinates) sit
next to the geometry parameters, so a cross vault is one command line instead of
six sequential questions. Density is asked at the end, with the fill density
only when the envelope actually has a fill.

Semantics are unchanged: see TNA_envelope.
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
from compas_tna.envelope import CrossVaultEnvelope
from compas_tna.envelope import DomeEnvelope
from compas_tna.envelope import Envelope
from compas_tna.envelope import MeshEnvelope
from compas_tna.envelope import PavillionVaultEnvelope
from compas_tna.envelope import PointedVaultEnvelope


def add_location(options):
    """Add the location options (shared by every parametric envelope)."""
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


def get_crossvault():
    options = add_location(Options("CrossVault"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_number("thickness", 0.5, minimum=0.0, maximum=100.0, keyword="Thickness")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return CrossVaultEnvelope(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        thickness=values["thickness"],
    )


def get_pointedvault():
    options = add_location(Options("PointedVault"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_number("rise", 3.0, minimum=0.0, maximum=1000.0, keyword="Rise")
    options.add_number("thickness", 0.5, minimum=0.0, maximum=100.0, keyword="Thickness")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return PointedVaultEnvelope(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        thickness=values["thickness"],
        hc=values["rise"],
    )


def get_pavilionvault():
    options = add_location(Options("PavilionVault"))
    options.add_number("x_size", 10.0, minimum=0.0, maximum=1000.0, keyword="XSize")
    options.add_number("y_size", 10.0, minimum=0.0, maximum=1000.0, keyword="YSize")
    options.add_number("thickness", 0.5, minimum=0.0, maximum=100.0, keyword="Thickness")
    options.add_number("angle", 45.0, minimum=0.0, maximum=90.0, keyword="SpringingAngle")

    values = options.get()
    if values is None:
        return None
    point = resolve_location(values)
    if point is None:
        return None

    return PavillionVaultEnvelope(
        x_span=(point[0], point[0] + values["x_size"]),
        y_span=(point[1], point[1] + values["y_size"]),
        thickness=values["thickness"],
        spr_angle=values["angle"],
    )


def get_dome():
    options = add_location(Options("Dome"))
    options.add_number("radius", 5.0, minimum=0.0, maximum=1000.0, keyword="Radius")
    options.add_number("thickness", 0.5, minimum=0.0, maximum=100.0, keyword="Thickness")
    options.add_integer("n_hoops", 10, minimum=1, maximum=100, keyword="Hoops")
    options.add_integer("n_parallels", 5, minimum=1, maximum=100, keyword="Parallels")
    options.add_number("r_oculus", 0.5, minimum=0.0, keyword="OculusRadius")

    values = options.get()
    if values is None:
        return None

    # the oculus bound depends on the radius, so it is checked after accepting
    if values["r_oculus"] >= values["radius"]:
        feedback.warn(f"Oculus radius ({values['r_oculus']}) must be smaller than the dome radius ({values['radius']}).")
        return None

    center = resolve_location(values)
    if center is None:
        return None

    return DomeEnvelope(
        center=center,
        radius=values["radius"],
        thickness=values["thickness"],
        n_hoops=values["n_hoops"],
        n_parallels=values["n_parallels"],
        r_oculus=values["r_oculus"],
    )


def get_from_middle():
    guid = compas_rhino.objects.select_mesh("Select middle surface")
    if not guid:
        return None

    mesh_middle = compas_rhino.conversions.meshobject_to_compas(guid)
    rs.UnselectAllObjects()

    options = Options("Middle surface")
    options.add_number("thickness", 0.5, minimum=0.0, maximum=100.0, keyword="Thickness")
    values = options.get()
    if values is None:
        return None

    rs.HideObject(guid)

    return MeshEnvelope.from_middle_mesh(mesh_middle, values["thickness"])


def get_from_bounds():
    guids_bounds = []

    guid = compas_rhino.objects.select_mesh("Select intrados")
    rs.UnselectAllObjects()
    if not guid:
        return None

    guids_bounds.append(guid)
    obj = compas_rhino.objects.find_object(guid)
    mesh_intrados = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)

    guid = compas_rhino.objects.select_mesh("Select extrados")
    rs.UnselectAllObjects()
    if not guid:
        return None

    guids_bounds.append(guid)
    obj = compas_rhino.objects.find_object(guid)
    mesh_extrados = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)

    guid = compas_rhino.objects.select_mesh("Select middle (Optional)")
    rs.UnselectAllObjects()
    if not guid:
        mesh_middle = None
    else:
        guids_bounds.append(guid)
        obj = compas_rhino.objects.find_object(guid)
        mesh_middle = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)

    guid = compas_rhino.objects.select_mesh("Select fill mesh (Optional)")
    rs.UnselectAllObjects()
    if not guid:
        mesh_fill = None
    else:
        guids_bounds.append(guid)
        obj = compas_rhino.objects.find_object(guid)
        mesh_fill = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)

    rs.HideObjects(guids_bounds)

    envelope = MeshEnvelope.from_meshes(mesh_intrados, mesh_extrados, mesh_middle)

    if mesh_fill:
        envelope.fill = mesh_fill  # type: ignore

    return envelope


LIBRARY = {
    "CrossVault": get_crossvault,
    "PointedVault": get_pointedvault,
    "PavilionVault": get_pavilionvault,
    "Dome": get_dome,
}


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    session["params"] = {}

    session.delete("envelope")
    session.delete("formdiagram")
    session.delete("analysis")

    for obj in session.scene.find_all_by_itemtype(Envelope):
        obj.clear()
        session.scene.remove(obj)

    for obj in session.scene.find_all_by_itemtype(FormDiagram):
        obj.clear()
        session.scene.remove(obj)

    session.scene.redraw()
    rs.Redraw()

    # =============================================================================
    # Create an envelope
    # =============================================================================

    envelope = None

    option = choose("Envelope", ["FromLibrary", "FromMiddle", "FromBounds"])
    if option is None:
        return

    if option == "FromLibrary":
        pattern = choose("Pattern", list(LIBRARY.keys()))
        if pattern is None:
            return
        envelope = LIBRARY[pattern]()

    elif option == "FromMiddle":
        envelope = get_from_middle()

    elif option == "FromBounds":
        envelope = get_from_bounds()

    else:
        raise NotImplementedError

    # =============================================================================
    # Commom parameters
    # =============================================================================

    if not envelope:
        feedback.warn("Error creating Envelope. Try again.")
        return

    options = Options("Densities")
    options.add_integer("rho", int(envelope.rho), minimum=0, maximum=200, keyword="Rho", prompt="Density masonry (rho)")
    if envelope.fill:
        options.add_integer("rho_fill", int(envelope.rho_fill), minimum=0, maximum=200, keyword="RhoFill", prompt="Density masonry fill (rho_fill)")

    values = options.get()
    if values is None:
        return

    envelope.rho = values["rho"]
    if envelope.fill:
        envelope.rho_fill = values["rho_fill"]

    # =============================================================================
    # Update scene
    # =============================================================================

    rs.UnselectAllObjects()

    session["envelope"] = envelope

    show_intrados = session.settings.envelope.show_intrados
    show_middle = session.settings.envelope.show_middle
    show_extrados = session.settings.envelope.show_extrados
    show_fill = session.settings.envelope.show_fill

    session.scene.add(envelope.intrados, disjoint=True, show=show_intrados, name="Intrados", layer="Masonry::TNA::Envelope")  # type: ignore
    session.scene.add(envelope.middle, disjoint=True, show=show_middle, name="Middle", layer="Masonry::TNA::Envelope")  # type: ignore
    session.scene.add(envelope.extrados, disjoint=True, show=show_extrados, name="Extrados", layer="Masonry::TNA::Envelope")  # type: ignore

    if envelope.fill:
        session.scene.add(envelope.fill, disjoint=True, show=show_fill, name="Fill", layer="Masonry::TNA::Envelope")  # type: ignore

    session.scene.redraw()
    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
