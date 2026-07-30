#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_create_options — create / duplicate / activate / delete a Problem.

Dev notes refactor:
- No string prompt on the first window: New/Duplicate/SetActive/Delete are
  command line options, and the problem name is a named option seeded with the
  next free "Problem_<n>" (accept it as is, or type a custom name).
- New layer hierarchy: a problem gets ONE layer, "Masonry::<index>_<name>",
  and no Loads / Boundary conditions sublayers. Boundary conditions own the loads, the
  boundary conditions and the results, and create their own subtree on demand
  (Problem_createbc).
- Deleting a problem renumbers the remaining problem layers so the index
  prefixes stay consecutive.

Problems created by the pre-BC commands keep their old
"Masonry::<name>::Loads|Boundary conditions" subtree; only problems created
here use the indexed hierarchy.
"""

import pathlib

from compas_dem.models import BlockModel
from compas_masonry.inputs import BACK
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm
from compas_rui.feedback import warn


def get_name(session, default=None):
    """Ask for the problem name, seeded with the next free one.

    Returns the name, BACK, or None if cancelled.
    """
    options = Options("Problem name", back=True)
    options.add_text("name", default or session.next_problem_name(), keyword="Name")

    values = options.get()
    if values is None or values is BACK:
        return values

    name = (values["name"] or "").strip()
    if not name:
        warn("A problem needs a name.")
        return None
    if name in session.problems:
        warn(f"There is already a problem called {name}.")
        return None
    return name


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    while True:
        options = ["New", "Duplicate", "SetActive", "RefreshSupports", "Delete"] if session.problems else ["New"]
        option = choose("Problem_create", options, default="New")
        if option is None:
            return

        # =============================================================================
        # RefreshSupports (keeps the problem; re-imports Block.is_support)
        # =============================================================================

        if option == "RefreshSupports":
            name = session.choose_problem(message="Problem to refresh the supports of", keywords=True)
            if name is None:
                return

            before, after = session.refresh_problem_supports(name, model)
            if before == after:
                print(f"{name}: supports unchanged ({len(after)} block(s)).")
            else:
                added = sorted(set(after) - set(before))
                removed = sorted(set(before) - set(after))
                print(f"{name}: supports refreshed, {len(before)} -> {len(after)} block(s).")
                if added:
                    print(f"  added:   {', '.join(str(i) for i in added)}")
                if removed:
                    print(f"  removed: {', '.join(str(i) for i in removed)}")
                print(f"  applied to {len(session.problems[name].boundary_conditions)} boundary condition(s); prescribed displacements kept.")
            session.draw_problem_bcs(name, model)
            return

        # =============================================================================
        # New
        # =============================================================================

        if option == "New":
            name = get_name(session)
            if name is BACK:
                continue
            if name is None:
                return

            problem = session.create_problem(model, name=name, sublayers=False)
            print(f"Created {problem.name} (active), layer {session.indexed_problem_layer(name)}.")
            print("NOTE: supports are IMPORTED from the model (Block.is_support). Edit them in Model_supports and refresh the problem.")
            print("Next: Problem_createbc to add a boundary condition — loads, boundary conditions and results live there.")
            return

        # =============================================================================
        # Duplicate (copies loads, BCs, contact model and solver of a source problem)
        # =============================================================================

        if option == "Duplicate":
            source_name = session.choose_problem(message="Problem to duplicate", keywords=True)
            if source_name is None:
                return

            name = get_name(session, default=f"{source_name}_copy")
            if name is BACK:
                continue
            if name is None:
                return

            source = session.problems[source_name]
            problem = session.create_problem(model, name=name, source=source, sublayers=False)
            print(f"Created {problem.name} as a duplicate of {source_name} (active).")
            return

        # =============================================================================
        # SetActive
        # =============================================================================

        if option == "SetActive":
            name = session.choose_problem(message="Problem to activate", keywords=True)
            if name is None:
                return

            session.set_active_problem(name)
            # Re-ensure the layer and regenerate the boundary condition geometry, so
            # activating a problem restores its layers even if they were deleted.
            session.ensure_indexed_problem_layer(name)
            session.draw_problem_bcs(name, model)
            print(f"Active problem: {name} (layers restored and redrawn).")
            return

        # =============================================================================
        # Delete (renumbers the remaining problem layers)
        # =============================================================================

        if option == "Delete":
            name = session.choose_problem(message="Problem to delete", keywords=True)
            if name is None:
                return

            if not confirm(f"Delete {name} and all its boundary conditions?"):
                return

            session.delete_problem(name, indexed=True)
            print(f"Deleted {name}. Remaining problem layers renumbered.")
            return


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
