#! python3
# venv: brg-csd
# r: compas_masonry

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.scene import RhinoFormDiagramObject
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tno.analysis import Analysis


def RunCommand():
    session = Session()

    formdiagram = session["formdiagram"]
    envelope = session["envelope"]

    if not formdiagram:
        feedback.warn("There is no FormDiagram. Please create one first.")
        return

    if not envelope:
        feedback.warn("There is no Envelope. Please create one first.")
        return

    # =============================================================================
    # Create an analysis
    # =============================================================================

    objective = rs.GetString(
        message="Objective",
        strings=[
            "MinimumThrust",
            "MinimumThickness",
            "MaximumThrust",
            "MaximumLoad",
            "Bestfit",
        ],
    )
    if not objective:
        return

    if objective == "MinimumThrust":
        analysis = Analysis.create_minthrust_analysis(formdiagram, envelope)

    elif objective == "MinimumThickness":
        analysis = Analysis.create_minthk_analysis(formdiagram, envelope)

    elif objective == "MaximumThrust":
        analysis = Analysis.create_maxthrust_analysis(formdiagram, envelope)

    elif objective == "MaximumLoad":
        analysis = Analysis.create_max_load_analysis(formdiagram, envelope)

    elif objective == "Bestfit":
        analysis = Analysis.create_bestfit_analysis(formdiagram, envelope)

    else:
        raise NotImplementedError

    analysis.apply_selfweight()
    analysis.apply_envelope()
    analysis.set_up_optimiser()
    analysis.run()

    # =============================================================================
    # Update scene
    # =============================================================================

    rs.UnselectAllObjects()

    formobject: RhinoFormDiagramObject = session.scene.find_by_itemtype(FormDiagram)  # type: ignore
    if not formobject:
        session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore

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
