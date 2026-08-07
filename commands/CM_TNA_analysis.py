#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""TNA_analysis_options — RhinoCommon variant of TNA_analysis.

The objective is a command line pick, and the two interactive loops collect
their values in one prompt each:
- MaximumLoad     : Force + "MoreVertices" toggle together.
- SupportDisplacement : Ux/Uy/Uz + "MoreVertices" toggle together.

Solver setup, post-solve messages and scene update are identical to TNA_analysis.
"""

import pathlib

import numpy as np
import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.scene import RhinoFormDiagramObject
from compas_masonry.session import MasonrySession as Session
from compas_rui import feedback
from compas_tna.diagrams import FormDiagram
from compas_tna.envelope import MeshEnvelope
from compas_tno.analysis import Analysis

OBJECTIVES = [
    "MinimumThrust",
    "MinimumThickness",
    "MaximumThrust",
    "MaximumLoad",
    "SupportDisplacement",
    "Bestfit",
]


def get_load():
    """Load magnitude + whether to keep assigning, in one prompt."""
    options = Options("Load to assign to selected vertices (negative downwards)")
    options.add_number("force", -10.0, keyword="Force")
    options.add_toggle("more", False, off="No", on="Yes", keyword="MoreVertices", prompt="Apply loads on additional vertices")
    return options.get()


def get_displacement():
    """Support displacement vector + whether to keep assigning, in one prompt."""
    options = Options("Support displacement [Ux, Uy, Uz]")
    options.add_number("ux", -1.0, keyword="Ux")
    options.add_number("uy", -1.0, keyword="Uy")
    options.add_number("uz", 0.0, keyword="Uz")
    options.add_toggle("more", False, off="No", on="Yes", keyword="MoreVectors", prompt="Define additional displacement vectors")
    return options.get()


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    formdiagram = session.get("formdiagram")
    envelope = session.get("envelope")

    if not formdiagram:
        feedback.warn("There is no FormDiagram")
        return

    if not envelope:
        feedback.warn("There is no Envelope")
        return

    formobject: RhinoFormDiagramObject = session.scene.find_by_itemtype(FormDiagram)  # type: ignore
    if not formobject:
        session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore

    formobject.redraw()

    sum_loads = sum(formobject.diagram.vertices_attribute("pz"))  # type: ignore
    if abs(sum_loads) < 0.001:
        feedback.warn("There are no loads applied to the model. Please assign loads.")
        return

    # =============================================================================
    # Create an analysis
    # =============================================================================

    objective = choose("Objective", OBJECTIVES)
    if objective is None:
        return

    if objective == "MinimumThrust":
        analysis = Analysis.create_minthrust_analysis(formdiagram, envelope)

    elif objective == "MinimumThickness":
        if isinstance(envelope, MeshEnvelope):
            feedback.warn("Minimum thickness analysis is only available for parametric envelopes")
            return

        analysis = Analysis.create_minthk_analysis(formdiagram, envelope)

    elif objective == "MaximumThrust":
        analysis = Analysis.create_maxthrust_analysis(formdiagram, envelope)

    elif objective == "MaximumLoad":
        n = formobject.diagram.number_of_vertices()
        load_direction = np.zeros((n, 1))
        index_vertex = formobject.diagram.index_vertex()

        while True:
            formobject.show_vertices = list(formobject.vertices())  # type: ignore
            formobject.redraw()

            vertices = formobject.select_vertices()

            if not vertices:
                break

            values = get_load()
            if values is None or not values["force"]:
                break

            for vertex in vertices:
                load_direction[index_vertex[vertex]] = values["force"]

            # Here we should add a vector to the Scene showing the load case that we are maximizing.

            rs.UnselectAllObjects()

            if not values["more"]:
                break

        analysis = Analysis.create_max_load_analysis(formdiagram, envelope, load_direction=load_direction, solver="SLSQP", max_lambd=9999)

    elif objective == "SupportDisplacement":
        supports = list(formobject.diagram.supports())
        nb = len(supports)
        displacement_array = np.zeros((nb, 3))

        while True:
            formobject.show_vertices = supports
            formobject.redraw()

            vertices = formobject.select_vertices()

            if not vertices:
                break

            values = get_displacement()
            if values is None:
                return

            displ_list = [values["ux"], values["uy"], values["uz"]]

            for vertex in vertices:
                displacement_array[supports.index(vertex)] = np.array(displ_list)
                print("Applied Vector {0} to support {1}".format(displ_list, vertex))

            # Here we should add a vector to the Scene showing the displacement that we are maximizing.

            rs.UnselectAllObjects()

            if not values["more"]:
                break

        analysis = Analysis.create_compl_energy_analysis(formdiagram, envelope, solver="SLSQP", support_displacement=displacement_array)

    elif objective == "Bestfit":
        analysis = Analysis.create_bestfit_analysis(formdiagram, envelope)

    else:
        raise NotImplementedError

    analysis.optimiser.settings["printout"] = True  # need to be true so people see the fopt.
    analysis.set_up_optimiser()
    analysis.run()

    # =============================================================================
    # Post Solver Messages
    # =============================================================================

    fopt = analysis.optimiser.fopt

    if objective == "MaximumLoad":
        print("Maximum Load Multipled to the loads assigned: {0:.3f}".format(fopt))
    elif objective == "MinimumThrust" or objective == "MaximumThrust":
        print("Optimal Horizontal Thrust Calculated: {0:.3f}".format(fopt))
    elif objective == "MinimumThickness":
        print("Minimum Thickness Calculated: {0:.3f}".format(fopt))
        # Update the envelope for smaller thickness check if it works
        if analysis.optimiser.exitflag == 0:
            envelope.thickness = fopt
            envelope.update_envelope()
    elif objective == "SupportDisplacement":
        print("Complementary Energy to Assigned Displacements: {0:.3f}".format(fopt))
    elif objective == "Bestfit":
        print("Optimal Squared vertical distance to middle surface: {0:.3f}".format(fopt))
    else:
        pass

    # =============================================================================
    # Update scene
    # =============================================================================

    rs.UnselectAllObjects()

    formobject: RhinoFormDiagramObject = session.scene.find_by_itemtype(FormDiagram)  # type: ignore

    if not formobject:
        session.scene.add(formdiagram, name="FormDiagram", layer="Masonry::TNA::FormDiagram")  # type: ignore

    session.settings.formdiagram.show_reactions = True
    session.settings.formdiagram.show_pipes = True

    formobject.redraw()

    rs.Redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
