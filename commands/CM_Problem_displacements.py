#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_displacements_options — prescribed displacements / rotations on a BOUNDARY CONDITION.

Same shape as Problem_addload: pick the problem, pick the boundary condition from a box,
then one window for the whole boundary condition.

`BoundaryCondition.add_displacement` takes dx/dy/dz *per component*, where None means
"this DOF is unconstrained" — which is not the same as prescribing 0.0. The
window mirrors that: a Constrain toggle per axis, and the value option for an
axis only appears when that axis is constrained. Rotations are a full vector
(`add_rotation`), so all three components are always shown.

Visualization: NO displaced copy of the geometry. A prescribed displacement is
an arrow, a prescribed rotation is a circle around its axis, both under the
boundary condition's "…::Displacements" layer.

Fixed supports are not edited here. They live on the model (Model_supports ->
Block.is_support), are carried by the problem, and are copied into every load
case when it is registered.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.boundaryconditions import bc_name
from compas_masonry.boundaryconditions import describe_entry
from compas_masonry.boundaryconditions import is_support
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def selected_nodes(session, model, message):
    guids = compas_rhino.objects.select_objects(message=message)
    if not guids:
        return []
    guid_element_map = session.guid_element_map(model)
    return sorted({n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None})


def add_bc(session, model, bc):
    def displacement(v):
        return v["kind"] == "Displacement"

    def rotation(v):
        return v["kind"] == "Rotation"

    def constrained(axis):
        return lambda v: displacement(v) and v[f"use_{axis}"]

    options = Options("Boundary condition")
    options.add_toggle("kind", False, off="Displacement", on="Rotation", text=True, keyword="Type")

    # per-component displacement: unconstrained (None) is a real, different state
    for axis in ("x", "y", "z"):
        options.add_toggle("use_" + axis, True, off="Free", on="Prescribed", keyword=f"Constrain{axis.upper()}", visible=displacement)
        options.add_number("d" + axis, 0.0, keyword=f"D{axis.upper()}", prompt=f"Displacement d{axis} [m]", visible=constrained(axis))

    for axis in ("x", "y", "z"):
        options.add_number("r" + axis, 0.0, keyword=f"R{axis.upper()}", prompt=f"Rotation r{axis} [rad]", visible=rotation)

    values = options.get()
    if values is None:
        return False

    if values["kind"] == "Displacement":
        components = {axis: (values["d" + axis] if values["use_" + axis] else None) for axis in ("x", "y", "z")}

        if all(v is None for v in components.values()):
            warn("Every axis is free — nothing to prescribe.")
            return False
        if all(v == 0.0 for v in components.values()):
            warn("A prescribed [0, 0, 0] displacement is a fixed support. Use Model_supports for that.")
            return False

        nodes = selected_nodes(session, model, "Select blocks for the displacement")
        if not nodes:
            return False

        for node in nodes:
            bc.add_displacement(block_index=node, dx=components["x"], dy=components["y"], dz=components["z"])

        shown = [("free" if v is None else f"{v:g}") for v in components.values()]
        print(f"Added displacement [{', '.join(shown)}] to {len(nodes)} block(s).")
        return True

    vector = [values["rx"], values["ry"], values["rz"]]
    if not any(vector):
        warn("A prescribed [0, 0, 0] rotation is a fixed support. Use Model_supports for that.")
        return False

    nodes = selected_nodes(session, model, "Select blocks for the rotation")
    if not nodes:
        return False

    for node in nodes:
        bc.add_rotation(block_index=node, rotation=vector)
    print(f"Added rotation {vector} to {len(nodes)} block(s).")
    return True


def remove_bc(bc):
    # the property returns the underlying list, so popping edits the boundary condition
    displacements = bc.displacements

    # supports are copied in from the problem and are not editable here
    removable = [(i, e) for i, e in enumerate(displacements) if not is_support(e)]
    if not removable:
        warn("No prescribed displacements/rotations to remove (supports are managed in Model_supports).")
        return False

    labels = [f"{pos}: {describe_entry(e)}" for pos, (i, e) in enumerate(removable)]
    label = rs.ListBox(labels, message="Entry to remove", title="Boundary conditions")
    if not label:
        return False

    original_index = removable[int(label.split(":")[0])][0]
    removed = displacements.pop(original_index)
    print(f"Removed BC: {describe_entry(removed)}")
    return True


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to edit BCs on", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    if not problem.boundary_conditions:
        return warn(f"{name} has no boundary condition. Run Problem_createbc first — boundary conditions belong to a boundary condition.")

    picked = session.choose_bc(problem, message="Boundary condition to prescribe displacements on")
    if picked is None:
        return
    index, bc = picked

    # a Gravity or Loads BC is not the place for prescribed movements
    bc_kind = session.bc_kind(name, index)
    if not session.bc_allows(bc_kind, "displacement"):
        return warn(f"{bc_name(bc, index)} is a {bc_kind} boundary condition, so it takes no prescribed displacements. Use a Displacements or Mixed BC, or change its kind in Problem_createbc.")

    option = choose("Boundary conditions", ["Add", "Remove"], default="Add")
    if option is None:
        return

    changed = add_bc(session, model, bc) if option == "Add" else remove_bc(bc)
    if not changed:
        return

    session.save_problems()
    session.draw_bc(name, bc, index, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
