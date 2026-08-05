#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_displacements — prescribed displacements and rotations on a Problem.

Same shape as Problem_loads, on the 2026-08 compas_dem API: a prescribed movement
is a typed object (`Translation`, `Rotation`) registered directly on the problem.
There is no BoundaryCondition container to pick — a problem IS the load case.

Movements are *grouped* for display by their own name — "Displacement_1",
"Settlement" — one layer each under "…::BoundaryConditions::<group>". The group
is chosen in the same window as the movement: extend an existing one, or New.

`Translation` takes dx/dy/dz **per component**, where `None` means "this DOF is
unconstrained" — which is not the same as prescribing 0.0. The window mirrors
that: a Constrain toggle per axis, and an axis's value appears only when that
axis is constrained. `Rotation` is the same, with rx/ry/rz.

Visualization: NO displaced copy of the geometry. A prescribed translation is an
arrow, a prescribed rotation a circle around its axis. Results_show is what draws
displaced geometry.

**Fixed supports are not edited here.** They live on the model
(Model_supports -> `Block.is_support`) and the solvers read them from there.

⚠ **CRA and RBE cannot apply prescribed movements.** They solve for the
displacements of the free blocks; support blocks are excluded from the
equilibrium system entirely and have no displacement degrees of freedom, so a
settlement cannot be expressed. That is structural, not a missing feature. Those
are LMGC90 / PRD / BLA only — and none of those is installed in Rhino yet. This
command builds the movement anyway (an LMGC90 build is in the pipeline) and warns
when the problem's solver cannot apply it.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_dem.problem import Rotation
from compas_dem.problem import Translation
from compas_masonry.boundaryconditions import describe
from compas_masonry.boundaryconditions import group_name
from compas_masonry.boundaryconditions import group_names
from compas_masonry.boundaryconditions import next_group_name
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn

NEW = "New"

# Solvers that can apply a prescribed movement. CRA/RBE cannot — see the module
# docstring — and compas_dem raises rather than silently ignoring one.
DISPLACEMENT_SOLVERS = ("LMGC90", "PRD", "BLA")


def selected_nodes(session, model, message):
    guids = compas_rhino.objects.select_objects(message=message)
    if not guids:
        return []
    guid_element_map = session.guid_element_map(model)
    return sorted({n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None})


def warn_if_solver_cannot_apply(problem) -> None:
    """Say up front if this problem's solver will refuse the movement.

    Better here than at solve time: the user is about to spend effort defining
    something the configured solver cannot use.
    """
    solver = problem.solver
    name = getattr(solver, "name", None)
    if name is None:
        print("No solver set yet. Note that CRA and RBE cannot apply prescribed movements — use LMGC90, PRD or BLA.")
        return
    if name not in DISPLACEMENT_SOLVERS:
        warn(f"{name} cannot apply prescribed movements: it has no displacement degrees of freedom for support blocks.")
        print(f"  The movement will be stored, but solving with {name} will refuse it.")
        print(f"  Applying one needs {', '.join(DISPLACEMENT_SOLVERS)} — set it in Problem_setsolver.")


def ask_movement(problem):
    """Ask for the group and every movement field in one window."""

    def is_translation(v):
        return v["kind"] == "Translation"

    def is_rotation(v):
        return v["kind"] == "Rotation"

    def constrained(axis, rotational=False):
        test = is_rotation if rotational else is_translation
        return lambda v: test(v) and v[f"use_{axis}"]

    existing = group_names(problem, "displacement")

    options = Options("Prescribed movement")
    options.add_list("group", [NEW] + existing, keyword="Group")
    options.add_text("newgroup", next_group_name(problem, "displacement"), keyword="Name", visible=lambda v: v["group"] == NEW)

    options.add_list("kind", ["Translation", "Rotation"], keyword="Type")

    # per component: unconstrained (None) is not the same as a prescribed 0.0
    for axis in ("x", "y", "z"):
        options.add_toggle(f"use_{axis}", True, off="Free", on="Fixed", text=False, keyword=f"Constrain{axis.upper()}", visible=is_translation)
        options.add_number(f"d{axis}", 0.0, keyword=f"D{axis.upper()}", units="m", prompt=f"Prescribed d{axis}", visible=constrained(axis))

    for axis in ("x", "y", "z"):
        options.add_toggle(f"use_r{axis}", True, off="Free", on="Fixed", text=False, keyword=f"ConstrainR{axis.upper()}", visible=is_rotation)
        options.add_number(f"r{axis}", 0.0, keyword=f"R{axis.upper()}", units="rad", prompt=f"Prescribed r{axis}", visible=constrained(f"r{axis}", rotational=True))

    values = options.get()
    if values is None:
        return None

    group = values["newgroup"].strip() if values["group"] == NEW else values["group"]
    if not group:
        warn("A movement group needs a name.")
        return None
    values["group"] = group
    return values


def add_movement(session, model, problem, values):
    group = values["group"]

    nodes = selected_nodes(session, model, "Select blocks to prescribe a movement on")
    if not nodes:
        return False

    if values["kind"] == "Translation":
        # None where the axis is unconstrained — never 0.0, which would prescribe
        # a movement of exactly zero and pin the block
        components = {axis: (values[f"d{axis}"] if values[f"use_{axis}"] else None) for axis in ("x", "y", "z")}
        if all(v is None for v in components.values()):
            warn("Every axis is free, so there is nothing to prescribe.")
            return False
        for node in nodes:
            problem.add(Translation(block=node, dx=components["x"], dy=components["y"], dz=components["z"], name=group))
        print(f"Added a prescribed translation on {len(nodes)} block(s) to [{group}].")
    else:
        components = {axis: (values[f"r{axis}"] if values[f"use_r{axis}"] else None) for axis in ("x", "y", "z")}
        if all(v is None for v in components.values()):
            warn("Every axis is free, so there is nothing to prescribe.")
            return False
        for node in nodes:
            problem.add(Rotation(block=node, rx=components["x"], ry=components["y"], rz=components["z"], name=group))
        print(f"Added a prescribed rotation on {len(nodes)} block(s) to [{group}].")

    warn_if_solver_cannot_apply(problem)
    return True


def remove_movement(problem):
    movements = problem.displacements
    if not movements:
        warn("This problem carries no prescribed movements.")
        return False

    scope = choose("Remove", ["One", "Group"], default="One")
    if scope is None:
        return False

    conditions = problem.boundary_conditions

    if scope == "Group":
        groups = group_names(problem, "displacement")
        group = groups[0] if len(groups) == 1 else rs.ListBox(groups, message="Movement group to remove", title="Displacements")
        if not group:
            return False
        doomed = [bc for bc in movements if group_name(bc) == group]
        for bc in doomed:
            conditions.remove(bc)
        print(f"Removed {len(doomed)} prescribed movement(s) in group [{group}].")
        return True

    labels = [f"{i}: [{group_name(bc)}] {describe(bc)}" for i, bc in enumerate(movements)]
    label = rs.ListBox(labels, message="Prescribed movement to remove", title="Displacements")
    if not label:
        return False

    bc = movements[int(label.split(":")[0])]
    conditions.remove(bc)
    print(f"Removed {describe(bc)}")
    return True


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to prescribe a movement on", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    option = choose("Prescribed movements", ["Add", "Remove"], default="Add")
    if option is None:
        return

    if option == "Add":
        values = ask_movement(problem)
        if values is None:
            return
        changed = add_movement(session, model, problem, values)
    else:
        changed = remove_movement(problem)

    if not changed:
        return

    session.save_problems()
    session.draw_problem_conditions(name, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
