#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.4

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino
import compas_rhino.conversions
import compas_rhino.objects
from compas.datastructures import Mesh
from compas_masonry.session import MasonrySession as Session
from compas_tna.diagrams import FormDiagram

# from compas_rui import feedback
from compas_tna.envelope import CrossVaultEnvelope
from compas_tna.envelope import DomeEnvelope
from compas_tna.envelope import Envelope
from compas_tna.envelope import MeshEnvelope
from compas_tna.envelope import PavillionVaultEnvelope
from compas_tna.envelope import PointedVaultEnvelope


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

    option = rs.GetString(message="Envelope", strings=["FromLibrary", "FromMiddle", "FromBounds"])
    if not option:
        return

    # =============================================================================
    # From a tempalate in the library
    # =============================================================================

    if option == "FromLibrary":
        option = rs.GetString(message="Choose a pattern", strings=["CrossVault", "PointedVault", "PavilionVault", "Dome"])
        if not option:
            return

        # =============================================================================
        # CrossVault
        # =============================================================================

        if option == "CrossVault":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
                return

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            envelope = CrossVaultEnvelope(
                x_span=x_span,
                y_span=y_span,
                thickness=thickness,
            )

        # =============================================================================
        # PointedVault
        # =============================================================================

        elif option == "PointedVault":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            rise = rs.GetReal("Rise", 3, 0.0, 1000)
            if not rise:
                return

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
                return

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            envelope = PointedVaultEnvelope(
                x_span=x_span,
                y_span=y_span,
                thickness=thickness,
                hc=rise,
            )

        # =============================================================================
        # PavilionVault
        # =============================================================================

        elif option == "PavilionVault":
            point = get_location()
            if not point:
                return

            x_size = rs.GetReal("X Size", 10, 0.0, 1000)
            if not x_size:
                return

            y_size = rs.GetReal("Y Size", 10, 0.0, 1000)
            if not y_size:
                return

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
                return

            angle = rs.GetReal("Springing Angle", 45, 0.0, 90)
            angle = angle or 0

            x_span = (point[0], point[0] + x_size)
            y_span = (point[1], point[1] + y_size)

            envelope = PavillionVaultEnvelope(
                x_span=x_span,
                y_span=y_span,
                thickness=thickness,
                spr_angle=angle,
            )

        # =============================================================================
        # Dome
        # =============================================================================

        elif option == "Dome":
            center = get_location()
            if not center:
                return

            radius = rs.GetReal("Radius", 5, 0.0, 1000)
            if not radius:
                return

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
                return

            n_hoops = rs.GetInteger("Number of hoops", 10, 1, 100)
            if not n_hoops:
                return

            n_parallels = rs.GetInteger("Number of parallels", 5, 1, 100)
            if not n_parallels:
                return

            r_oculus = rs.GetReal("Oculus radius", 0.5, 0.0, radius)
            if r_oculus is None:
                return

            envelope = DomeEnvelope(
                center=center,
                radius=radius,
                thickness=thickness,
                n_hoops=n_hoops,
                n_parallels=n_parallels,
                r_oculus=r_oculus,
            )

        # =============================================================================
        # Not supported
        # =============================================================================

        else:
            raise NotImplementedError

    # =============================================================================
    # From the middle surface
    # =============================================================================

    elif option == "FromMiddle":
        guid = compas_rhino.objects.select_mesh("Select middle surface")
        if not guid:
            return

        mesh_middle = compas_rhino.conversions.meshobject_to_compas(guid)
        rs.UnselectAllObjects()

        thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
        if not thickness:
            return

        rs.HideObject(guid)

        envelope = MeshEnvelope.from_middle_mesh(mesh_middle, thickness)

    # # =============================================================================
    # # From the intrados mesh - This is not available yet. I would not show.
    # # =============================================================================

    # elif option == "FromIntrados":
    #     # select the intrados mesh
    #     # specify the thickness
    #     # compute the envelope
    #     pass

    # =============================================================================
    # From the intrados and extrados meshes
    # =============================================================================

    elif option == "FromBounds":
        guids_bounds = []

        guid = compas_rhino.objects.select_mesh("Select intrados")
        rs.UnselectAllObjects()
        if not guid:
            return

        guids_bounds.append(guid)
        obj = compas_rhino.objects.find_object(guid)
        mesh_intrados = compas_rhino.conversions.mesh_to_compas(obj.Geometry, cls=Mesh)

        guid = compas_rhino.objects.select_mesh("Select extrados")
        rs.UnselectAllObjects()
        if not guid:
            return

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

        rs.HideObjects(guids_bounds)

        envelope = MeshEnvelope.from_meshes(mesh_intrados, mesh_extrados, mesh_middle)

    # =============================================================================
    # Not supported
    # =============================================================================

    else:
        raise NotImplementedError

    # =============================================================================
    # Update scene
    # =============================================================================

    rs.UnselectAllObjects()

    if not envelope:
        return

    session["envelope"] = envelope

    show_intrados = session.settings.envelope.show_intrados
    show_middle = session.settings.envelope.show_middle
    show_extrados = session.settings.envelope.show_extrados

    session.scene.add(envelope.intrados, disjoint=True, show=show_intrados, name="Intrados", layer="Masonry::TNA::Envelope")  # type: ignore
    session.scene.add(envelope.middle, disjoint=True, show=show_middle, name="Middle", layer="Masonry::TNA::Envelope")  # type: ignore
    session.scene.add(envelope.extrados, disjoint=True, show=show_extrados, name="Extrados", layer="Masonry::TNA::Envelope")  # type: ignore

    session.scene.redraw()
    rs.Redraw()

    # =============================================================================
    # Save
    # =============================================================================

    # if session.settings.autosave:
    #     session.record(name="Envelope")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
