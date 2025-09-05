#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_session.lazyload import LazyLoadSession as Session
from compas_tna.envelope import CrossVaultEnvelope
from compas_tna.envelope import DomeEnvelope
from compas_tna.envelope import Envelope


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    envelopeobject = session.scene.find_by_itemtype(Envelope)
    if envelopeobject:
        envelopeobject.clear()
        session.scene.remove(envelopeobject)

    session.delete("envelope")

    # =============================================================================
    # Create an envelope
    # =============================================================================

    envelope = None

    # =============================================================================
    # Dome
    # =============================================================================

    if session["params"]["formdiagram"] == "circular":
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
    # Cross
    # =============================================================================

    elif session["params"]["formdiagram"] == "cross":
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
    # Fan
    # =============================================================================

    elif session["params"]["formdiagram"] == "fan":
        x_span = session["params"]["x_span"]
        y_span = session["params"]["y_span"]
        n_fans = session["params"]["n_fans"]
        n_hoops = session["params"]["n_hoops"]

        raise NotImplementedError

    # =============================================================================
    # Ortho
    # =============================================================================

    elif session["params"]["formdiagram"] == "ortho":
        x_span = session["params"]["x_span"]
        y_span = session["params"]["y_span"]
        nx = session["params"]["nx"]
        ny = session["params"]["ny"]

        raise NotImplementedError

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

    session.scene.add(envelope.intrados, name="Intrados", layer="Masonry::TNA::Envelope::Intrados")  # type: ignore
    session.scene.add(envelope.middle, name="Middle", layer="Masonry::TNA::Envelope::Middle")  # type: ignore
    session.scene.add(envelope.extrados, name="Extrados", layer="Masonry::TNA::Envelope::Extrados")  # type: ignore

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
