#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_loads — add and remove loads on a Problem.

Renamed from Problem_addload, and rebuilt on the 2026-08 compas_dem API.

**A problem IS the load case.** There is no BoundaryCondition container to pick
any more: a load is a typed object (`PointLoad`, `Moment`, `SurfaceLoad`,
`BodyForce`) registered directly on the problem. Solving applies every one of
them; a different set of loads means a different problem.

Loads are still *grouped* for display, by their own name — "Load_1", "Wind" —
and each group gets its own layer under "…::BoundaryConditions::<group>". The
group is chosen in the same window as the load itself: pick an existing one to
extend it, or New to start another.

Load types:

- **Point** — a force on one block, at a **vertex** or at the **centroid of a
  face**. compas_dem also offers an arbitrary point and the block centroid; the
  Rhino UI deliberately offers only these two (the summer-school decision), since
  they are the two a user can actually see and click.
- **Surface** — a traction on one or more faces of one block. compas_dem
  multiplies by the face area, so this is a pressure, not a total force.
- **Moment** — a couple on one block, with no net force.
- **BodyForce** — an acceleration applied to every block by its mass: a rotated
  gravity for a tilted table, or a static seismic load. Gravity itself is applied
  by the solver from block density, so this carries only the ADDED component.

Two things that used to be here and are gone:

- **Gravity is not a load.** `bc.g` never did anything — self-weight is applied
  unconditionally from block density — so there is no Gravity option and no
  gravity arrow to clear.
- **BodyForce is no longer expanded by hand.** It used to be written as one
  centroid point load per block, because `add_global_body_force` was not
  honoured by the solvers. `resolve_centroidal_loads` now handles `BodyForce`
  natively and mass-weights it, so the expansion (and the `AllPoint` removal it
  forced) is deleted.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_dem.problem import BodyForce
from compas_dem.problem import Moment
from compas_dem.problem import PointLoad
from compas_dem.problem import SurfaceLoad
from compas_masonry.boundaryconditions import describe
from compas_masonry.boundaryconditions import group_name
from compas_masonry.boundaryconditions import group_names
from compas_masonry.boundaryconditions import next_group_name
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn

NEW = "New"


def selected_nodes(session, model, message):
    """Select Rhino block objects and resolve them to graph node indices."""
    guids = compas_rhino.objects.select_objects(message=message)
    if not guids:
        return []
    guid_element_map = session.guid_element_map(model)
    return sorted({n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None})


def label_faces(block):
    """Temporarily label every face of a block with its index."""
    mesh = block.modelgeometry
    guids = []
    for face in mesh.faces():
        guid = rs.AddTextDot(str(face), mesh.face_centroid(face))
        if guid:
            guids.append(guid)
    rs.Redraw()
    return guids


def label_vertices(block):
    """Temporarily label every vertex of a block with its index."""
    mesh = block.modelgeometry
    guids = []
    for vertex in mesh.vertices():
        guid = rs.AddTextDot(str(vertex), mesh.vertex_point(vertex))
        if guid:
            guids.append(guid)
    rs.Redraw()
    return guids


def parse_faces(text, nfaces):
    """Parse "0, 3 5" / "all" into a sorted list of valid face indices.

    Returns (faces, rejected). Anything out of range or unparseable comes back in
    `rejected`, so the caller can say which entries were dropped rather than
    silently loading the wrong faces.
    """
    text = (text or "").strip()
    if text.lower() in ("all", "*"):
        return list(range(nfaces)), []

    faces, rejected = [], []
    for token in text.replace(",", " ").split():
        try:
            index = int(token)
        except ValueError:
            rejected.append(token)
            continue
        if 0 <= index < nfaces:
            faces.append(index)
        else:
            rejected.append(token)

    return sorted(set(faces)), rejected


def pick_indices(block, what):
    """Ask for face or vertex indices while they are labelled in the viewport.

    `what` is "face" or "vertex". Faces accept several ("0,3,5" or "all") because
    a surface load often covers a whole side; a vertex anchor takes the first.

    A temporary TextDot per item is the current mechanism. Picking the geometry
    directly (sub-object selection) is the intended replacement — see
    temp/status_pending_work.md §4.1 — and nothing upstream provides it yet.
    """
    mesh = block.modelgeometry
    if what == "face":
        count = mesh.number_of_faces()
        labels = label_faces(block)
    else:
        count = mesh.number_of_vertices()
        labels = label_vertices(block)

    try:
        options = Options(f"{what.capitalize()} index of the selected block (0..{count - 1})")
        options.add_text("picked", "0", keyword=what.capitalize())
        values = options.get()
    finally:
        # the labels are a temporary aid, never leave them in the document
        if labels:
            rs.DeleteObjects(labels)
            rs.Redraw()

    if values is None:
        return None

    picked, rejected = parse_faces(values["picked"], count)
    if rejected:
        warn(f"Ignored {', '.join(rejected)}: not a {what} index in 0..{count - 1}.")
    if not picked:
        warn(f"No valid {what} index given.")
        return None
    return picked


def ask_load(problem):
    """Ask for the group and every load field in one window.

    The group field is what makes "extend or start a new one" a choice rather
    than a separate prompt: pick an existing group to add to it, or New and give
    a name.
    """

    def is_(*kinds):
        return lambda v: v["kind"] in kinds

    existing = group_names(problem, "load")
    choices = [NEW] + existing

    options = Options("Add load")
    options.add_list("group", choices, keyword="Group")
    options.add_text("newgroup", next_group_name(problem, "load"), keyword="Name", visible=lambda v: v["group"] == NEW)

    options.add_list("kind", ["Point", "Surface", "Moment", "BodyForce"], keyword="LoadType")

    # where a point load acts. compas_dem also has at_point and at_centroid; only
    # the two a user can see and click are offered here.
    options.add_list("anchor", ["Vertex", "Face"], keyword="At", visible=is_("Point"))

    options.add_number("fx", 0.0, keyword="Fx", units="N", prompt="Force fx", visible=is_("Point"))
    options.add_number("fy", 0.0, keyword="Fy", units="N", prompt="Force fy", visible=is_("Point"))
    options.add_number("fz", -1000.0, keyword="Fz", units="N", prompt="Force fz", visible=is_("Point"))

    # a traction: compas_dem multiplies by the face area, so this is a pressure
    options.add_number("tx", 0.0, keyword="Tx", units="N/m2", prompt="Traction tx", visible=is_("Surface"))
    options.add_number("ty", 0.0, keyword="Ty", units="N/m2", prompt="Traction ty", visible=is_("Surface"))
    options.add_number("tz", -1000.0, keyword="Tz", units="N/m2", prompt="Traction tz", visible=is_("Surface"))

    options.add_number("mx", 0.0, keyword="Mx", units="Nm", prompt="Moment mx", visible=is_("Moment"))
    options.add_number("my", 0.0, keyword="My", units="Nm", prompt="Moment my", visible=is_("Moment"))
    options.add_number("mz", 0.0, keyword="Mz", units="Nm", prompt="Moment mz", visible=is_("Moment"))

    options.add_number("ax", 0.0, keyword="Ax", units="m/s2", prompt="Acceleration ax", visible=is_("BodyForce"))
    options.add_number("ay", 0.0, keyword="Ay", units="m/s2", prompt="Acceleration ay", visible=is_("BodyForce"))
    options.add_number("az", 0.0, keyword="Az", units="m/s2", prompt="Acceleration az", visible=is_("BodyForce"))

    # time-series shape, straight from the compas_dem load classes
    options.add_toggle("loading", False, off="Ramp", on="Instantaneous", text=True, keyword="Loading")

    values = options.get()
    if values is None:
        return None

    group = values["newgroup"].strip() if values["group"] == NEW else values["group"]
    if not group:
        warn("A load group needs a name.")
        return None
    values["group"] = group
    return values


def add_load(session, model, problem, values):
    """Build the load object(s) and register them on the problem."""
    kind = values["kind"]
    group = values["group"]
    loading_type = values["loading"].lower()

    if kind == "BodyForce":
        acceleration = [values["ax"], values["ay"], values["az"]]
        if not any(acceleration):
            warn("A body force needs a non-zero acceleration.")
            return False
        problem.add(BodyForce(acceleration=acceleration, loading_type=loading_type, name=group))
        print(f"Added body force {acceleration} m/s2 to [{group}] — applied to every block by its mass.")
        print("  Gravity is applied by the solver from block density, so this is the ADDED component only.")
        return True

    nodes = selected_nodes(session, model, f"Select ONE block for the {kind.lower()} load")
    if not nodes:
        return False
    node = nodes[0]
    if len(nodes) > 1:
        warn(f"{len(nodes)} blocks selected; using block {node}.")

    if kind == "Moment":
        moment = [values["mx"], values["my"], values["mz"]]
        if not any(moment):
            warn("A moment needs a non-zero value.")
            return False
        problem.add(Moment(block=node, moment=moment, loading_type=loading_type, name=group))
        print(f"Added moment {moment} Nm on block {node} to [{group}].")
        return True

    block = model.graph.node_element(node)

    if kind == "Point":
        force = [values["fx"], values["fy"], values["fz"]]
        if not any(force):
            warn("A point load needs a non-zero force.")
            return False

        what = "vertex" if values["anchor"] == "Vertex" else "face"
        picked = pick_indices(block, what)
        if not picked:
            return False
        index = picked[0]
        if len(picked) > 1:
            warn(f"Several {what}s given; using {index}.")

        if what == "vertex":
            problem.add(PointLoad.at_vertex(block=node, vertex=index, force=force, loading_type=loading_type, name=group))
        else:
            problem.add(PointLoad.at_face(block=node, face=index, force=force, loading_type=loading_type, name=group))
        print(f"Added point load {force} N on block {node} at {what} {index} to [{group}].")
        return True

    if kind == "Surface":
        traction = [values["tx"], values["ty"], values["tz"]]
        if not any(traction):
            warn("A surface load needs a non-zero traction.")
            return False

        faces = pick_indices(block, "face")
        if not faces:
            return False

        # SurfaceLoad takes a single face, so a multi-face pick is one object per
        # face — each keeps its own area when the solver resolves it
        for face in faces:
            problem.add(SurfaceLoad(block=node, face=face, traction=traction, loading_type=loading_type, name=group))
        listed = ", ".join(str(f) for f in faces)
        print(f"Added surface load {traction} N/m2 on block {node}, face(s) {listed}, to [{group}].")
        print("  A traction is multiplied by the face area, so this is a pressure, not a total force.")
        return True

    return False


def remove_load(problem):
    """Remove loads, either one at a time or a whole group at once."""
    loads = problem.loads
    if not loads:
        warn("This problem carries no loads.")
        return False

    scope = choose("Remove", ["One", "Group"], default="One")
    if scope is None:
        return False

    conditions = problem.boundary_conditions

    if scope == "Group":
        groups = group_names(problem, "load")
        group = groups[0] if len(groups) == 1 else rs.ListBox(groups, message="Load group to remove", title="Loads")
        if not group:
            return False
        doomed = [bc for bc in loads if group_name(bc) == group]
        for bc in doomed:
            conditions.remove(bc)
        print(f"Removed {len(doomed)} load(s) in group [{group}].")
        return True

    labels = [f"{i}: [{group_name(bc)}] {describe(bc)}" for i, bc in enumerate(loads)]
    label = rs.ListBox(labels, message="Load to remove", title="Loads")
    if not label:
        return False

    bc = loads[int(label.split(":")[0])]
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

    name = session.choose_problem(message="Problem to add a load to", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    option = choose("Loads", ["Add", "Remove"], default="Add")
    if option is None:
        return

    if option == "Add":
        values = ask_load(problem)
        if values is None:
            return
        changed = add_load(session, model, problem, values)
    else:
        changed = remove_load(problem)

    if not changed:
        return

    session.save_problems()
    session.draw_problem_conditions(name, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
