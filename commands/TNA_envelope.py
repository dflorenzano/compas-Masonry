#! python3
# venv: brg-csd
# r: compas_masonry

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.envelope import CrossVaultEnvelope
from compas_tna.envelope import DomeEnvelope
from compas_tna.envelope import Envelope
from compas_tna.envelope import PavillionVaultEnvelope
from compas_tna.envelope import PointedVaultEnvelope


def RunCommand():
    session = Session()

    formdiagram = session["formdiagram"]

    if not formdiagram:
        feedback.warn("There is no FormDiagram. Please create one first.")
        return

    session.delete("envelope")

    obj = session.scene.find_by_itemtype(Envelope)
    if obj:
        obj.clear()
        session.scene.remove(obj)

    # =============================================================================
    # Create an envelope
    # =============================================================================

    envelope = None

    option = rs.GetString(message="Envelope", strings=["FromLibrary", "FromMiddle", "FromIntrados", "FromBounds"])
    if not option:
        return

    if option == "FromLibrary":
        option = rs.GetString(message="Choose a pattern", strings=["CrossVault", "PointedVault", "PavilionVault", "Dome"])
        if not option:
            return

        # =============================================================================
        # CrossVault
        # =============================================================================

        if option == "CrossVault":
            x_span = session["params"]["x_span"]
            y_span = session["params"]["y_span"]
            n = session["params"]["n"]

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
                return

            envelope = CrossVaultEnvelope(
                x_span=x_span,
                y_span=y_span,
                thickness=thickness,
                n=n,
            )

        # =============================================================================
        # PointedVault
        # =============================================================================

        elif option == "PointedVault":
            pass

        # =============================================================================
        # PavilionVault
        # =============================================================================

        elif option == "PavilionVault":
            pass

        # =============================================================================
        # Dome
        # =============================================================================

        elif option == "Dome":
            center = session["params"]["center"]
            radius = session["params"]["radius"]
            n_hoops = session["params"]["n_hoops"]
            n_parallels = session["params"]["n_parallels"]
            r_oculus = session["params"]["r_oculus"]

            thickness = rs.GetReal("Thickness", 0.5, 0.0, 100)
            if not thickness:
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
    # Middle
    # =============================================================================

    elif option == "FromMiddle":
        # select the middle surface mesh
        # specify the thickness
        # compute the envelope
        pass

    # =============================================================================
    # Intrados
    # =============================================================================

    elif option == "FromIntrados":
        # select the intrados mesh
        # specify the thickness
        # compute the envelope
        pass

    # =============================================================================
    # BoundsMeshes
    # =============================================================================

    elif option == "FromBounds":
        # select the intrados mesh
        # select the extrados mesh
        # compute the envelope
        pass

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

    envelope.apply_bounds_to_formdiagram(formdiagram)
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
