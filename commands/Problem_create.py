#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_create — create (or duplicate) an analysis Problem for the current BlockModel.

A model can carry many problems (same loads, different solver -> new problem);
the user owns that organisation. Each problem gets a Rhino layer subtree under
"Masonry::Problem_<n>::..." (Loads/Gravity|Point|Surface, Boundary
conditions/Displacements|Rotations). A fresh problem inherits the model's
`is_support` flags via add_supports_from_model; a duplicate deep-copies another
problem's loads, contact model and solver.

State lives in the session: `problems` (dict) + `active_problem`. See
MasonrySession.create_problem / draw_problem.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    options = ["New", "Duplicate", "SetActive"] if session.problems else ["New"]
    option = rs.GetString(message="Problem_create", strings=options)
    if not option:
        return

    # =============================================================================
    # New
    # =============================================================================

    if option == "New":
        problem = session.create_problem(model)
        print(f"Created {problem.name} (active).")
        print(
            "NOTE: supports are IMPORTED from the model (Block.is_support). "
            "To change which blocks are fixed, edit them in Model_supports and "
            "create/refresh the problem — they are not edited here."
        )

    # =============================================================================
    # Duplicate (copies loads, BCs, contact model and solver of a source problem)
    # =============================================================================

    elif option == "Duplicate":
        source_name = session.choose_problem(message="Problem to duplicate")
        if source_name is None:
            return
        source = session.problems[source_name]
        problem = session.create_problem(model, source=source)
        print(f"Created {problem.name} as a duplicate of {source_name} (active).")

    # =============================================================================
    # SetActive
    # =============================================================================

    elif option == "SetActive":
        name = session.choose_problem(message="Problem to activate")
        if name is None:
            return
        session.set_active_problem(name)
        # Re-ensure the layer tree and regenerate the geometry, so activating a
        # problem restores its layers/drawing even if they were deleted.
        session.ensure_problem_layers(name)
        session.draw_problem(name, model)
        print(f"Active problem: {name} (layers restored and redrawn).")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
