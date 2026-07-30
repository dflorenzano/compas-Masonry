#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_createbc_options — manage the boundary conditions of a Problem.

Every BC has a KIND — Gravity / Loads / Displacements / Mixed — picked in the
same window as its name. It decides what the BC may hold (enforced by
Problem_addload and Problem_displacements) and whether it carries gravity:
`BoundaryCondition` is constructed with `g=9.81`, so before this every new BC
came with a gravity load and drew a gravity arrow no matter what it was for.

The kind lives on the session (`session.bc_kinds`), not on the BC — compas_dem's
BoundaryCondition has no such field. It is keyed by index, so deleting a BC
reindexes the map.

A boundary condition owns its loads and its displacement BCs, and its results are drawn
under its own layer subtree, created here on demand:

    Masonry::<index>_<problem>::BC<n>_<name>::Loads
                                            ::Displacements
                                            ::Results

Operations: Create / Duplicate / Rename / Delete.

Two things about `Problem.add_boundary_condition` shape this command:
- The problem's supports are copied into the boundary condition when it is registered,
  so supports must exist on the problem first (Problem_create does that from
  the model's `is_support` flags).
- It returns the index to use, and it *replaces* the auto-created "default"
  boundary condition at index 0 if one exists — so the returned index is the only
  reliable one, never len(bcs) - 1.
"""

import pathlib

from compas_dem.models import BlockModel
from compas_dem.problem import BoundaryCondition
from compas_masonry.inputs import BACK
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.boundaryconditions import bc_name
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm
from compas_rui.feedback import warn


def next_bc_name(problem) -> str:
    """Next free "BC<n>" name for a problem."""
    existing = {bc_name(bc, i) for i, bc in enumerate(problem.boundary_conditions)}
    i = len(existing) + 1
    while f"BC{i}" in existing:
        i += 1
    return f"BC{i}"


def get_name_and_kind(default, kind=None):
    """Ask for the BC name and kind at once. Returns (name, kind), BACK, or None."""
    options = Options("Boundary condition", back=True)
    options.add_text("name", default, keyword="Name")
    options.add_list("kind", Session.BC_KINDS, index=Session.BC_KINDS.index(kind or Session.BC_KIND_DEFAULT), keyword="Kind")

    values = options.get()
    if values is None or values is BACK:
        return values

    name = (values["name"] or "").strip()
    if not name:
        warn("A boundary condition needs a name.")
        return None
    return name, values["kind"]


def apply_kind(bc, kind) -> None:
    """Make the BC's contents match its kind.

    A `BoundaryCondition` is constructed with `g=9.81`, so every new BC carried
    a gravity load and drew a gravity arrow whatever it was meant to represent.
    Only a Gravity (or Mixed) BC keeps it.

    Note this is a *flag*, not the physics: CRA and RBE apply self-weight
    internally from the block densities regardless of `bc.g`, so clearing it
    changes what is drawn and what the BC declares, not what those solvers do.
    """
    bc.g = 9.81 if kind in ("Gravity", "Mixed") else 0.0


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to edit boundary conditions on", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    while True:
        options = ["Create", "Duplicate", "Rename", "Delete"] if problem.boundary_conditions else ["Create"]
        option = choose("Boundary conditions", options, default="Create")
        if option is None:
            return

        # =============================================================================
        # Create
        # =============================================================================

        if option == "Create":
            answer = get_name_and_kind(next_bc_name(problem))
            if answer is BACK:
                continue
            if answer is None:
                return
            casename, kind = answer

            bc = BoundaryCondition(name=casename)
            apply_kind(bc, kind)
            index = problem.add_boundary_condition(bc)
            session.set_bc_kind(name, index, kind)

            # the layer subtree is created here, on demand — not with the problem
            session.ensure_bc_layers(name, casename, index)
            session.save_problems()
            session.draw_bc(name, bc, index, model)

            print(f"Created {kind} boundary condition {casename} on {name}: {session.bc_layer(name, casename, index)}")
            print(f"  {len(problem.supports)} support(s) copied in from the problem.")
            if bc.g:
                print(f"  gravity g = {bc.g} m/s2.")
            else:
                print("  no gravity: only a Gravity or Mixed BC carries it.")
                print("  (CRA and RBE still apply self-weight internally, from the block densities.)")
            print("Next: Problem_addload / Problem_displacements to fill it.")
            return

        # =============================================================================
        # Duplicate
        # =============================================================================

        if option == "Duplicate":
            picked = session.choose_bc(problem, message="Boundary condition to duplicate")
            if picked is None:
                return
            source_index, source = picked

            answer = get_name_and_kind(f"{bc_name(source, source_index)}_copy", kind=session.bc_kind(name, source_index))
            if answer is BACK:
                continue
            if answer is None:
                return
            casename, kind = answer

            bc = source.copy()  # compas Data: JSON round trip, fresh guid
            bc.name = casename
            apply_kind(bc, kind)
            index = problem.add_boundary_condition(bc)
            session.set_bc_kind(name, index, kind)

            session.ensure_bc_layers(name, casename, index)
            session.save_problems()
            session.draw_bc(name, bc, index, model)
            print(f"Duplicated boundary condition {bc_name(source, source_index)} as {casename} ({kind}).")
            return

        # =============================================================================
        # Rename
        # =============================================================================

        if option == "Rename":
            picked = session.choose_bc(problem, message="Boundary condition to rename")
            if picked is None:
                return
            index, bc = picked
            oldname = bc_name(bc, index)

            answer = get_name_and_kind(oldname, kind=session.bc_kind(name, index))
            if answer is BACK:
                continue
            if answer is None:
                return
            casename, kind = answer

            bc.name = casename
            apply_kind(bc, kind)
            session.set_bc_kind(name, index, kind)
            session.save_problems()
            # the layer name carries the index, so drop and regenerate the subtrees
            session.delete_all_bc_layers(name)
            session.draw_problem_bcs(name, model)
            print(f"Renamed boundary condition {oldname} to {casename}.")
            return

        # =============================================================================
        # Delete
        # =============================================================================

        if option == "Delete":
            picked = session.choose_bc(problem, message="Boundary condition to delete")
            if picked is None:
                return
            index, bc = picked
            casename = bc_name(bc, index)

            if not confirm(f"Delete boundary condition {casename} and its results?"):
                return

            problem.boundary_conditions.pop(index)
            # the kind map is keyed by index, so it shifts with the list
            session.reindex_bc_kinds(name, [i for i in range(len(problem.boundary_conditions) + 1) if i != index])
            session.save_problems()
            # every layer name carries an index, and the indices just shifted:
            # drop the whole set and regenerate it for the survivors
            session.delete_all_bc_layers(name)
            session.draw_problem_bcs(name, model)
            print(f"Deleted boundary condition {casename}.")
            return


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
