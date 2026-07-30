#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_addload_options — add/remove loads on a BOUNDARY CONDITION of a Problem.

Replaces Problem_loads_options: loads live on a boundary condition, not on the problem.

- The existing boundary conditions are listed in a box to pick from. No boundary condition is an
  error, not a prompt — run Problem_createbc first.
- Only the load types the BC's KIND accepts are offered (a Displacements BC
  takes none at all).
- Once a boundary condition is picked, every load field is shown in one window: the load
  type, the values, and the solver's loading type (ramp / instantaneous).
- SURFACE loads temporarily label every face of the selected block with its
  index, and accept SEVERAL faces ("0,3,5" or "all") — one entry per face.

Load types:

- **Gravity** — sets `bc.g`. Only on a Gravity or Mixed BC.
- **Point** — a force on each selected block, at its centroid.
- **Surface** — a traction on one or more faces of one block.
- **BodyForce** — an acceleration applied to EVERY block by its mass: a rotated
  gravity for a tilted test table, or a static seismic load. Expanded here into
  one centroid point load per block (`mass * a * direction`) rather than through
  `add_global_body_force`, so every solver that reads point loads honours it.

Loads are added straight through the compas_dem BoundaryCondition API
(`add_gravity`, `add_point_load`, `add_surface_load`). Geometry is regenerated
by session.draw_bc() under the boundary condition's "…::Loads" layer.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def selected_nodes(session, model, message):
    """Select Rhino block objects and resolve them to graph node indices."""
    guids = compas_rhino.objects.select_objects(message=message)
    if not guids:
        return []
    guid_element_map = session.guid_element_map(model)
    return sorted({n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None})


def label_faces(block):
    """Temporarily label every face of a block with its index.

    Returns the guids of the labels, to be deleted by the caller.
    """
    mesh = block.modelgeometry
    guids = []
    for face in mesh.faces():
        guid = rs.AddTextDot(str(face), mesh.face_centroid(face))
        if guid:
            guids.append(guid)
    rs.Redraw()
    return guids


def parse_faces(text, nfaces):
    """Parse "0, 3 5" / "all" into a sorted list of valid face indices.

    Returns (faces, rejected). Anything out of range or unparseable comes back
    in `rejected`, so the caller can say which entries were dropped rather than
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


def pick_faces(block):
    """Ask for one or more face indices while the faces are labelled in the viewport.

    A surface load often covers several faces (the whole extrados of a block,
    say), and `add_surface_load` takes one face at a time — so this accepts a
    list and the caller loops.
    """
    mesh = block.modelgeometry
    nfaces = mesh.number_of_faces()

    labels = label_faces(block)
    try:
        options = Options(f"Faces of the selected block (0..{nfaces - 1}, comma separated, or All)")
        options.add_text("faces", "0", keyword="Faces")
        values = options.get()
    finally:
        # the labels are a temporary aid, never leave them in the document
        if labels:
            rs.DeleteObjects(labels)
            rs.Redraw()

    if values is None:
        return None

    faces, rejected = parse_faces(values["faces"], nfaces)
    if rejected:
        warn(f"Ignored {', '.join(rejected)}: not a face index in 0..{nfaces - 1}.")
    if not faces:
        warn("No valid face index given.")
        return None
    return faces


def block_mass(block):
    """Mass of a block in [kg], or None if it has no material density.

    Same rule as `compas_dem.analysis.resolve._element_mass`: density times the
    volume of the model geometry.
    """
    material = block.material
    if material is None or material.density is None:
        return None
    return material.density * block.modelgeometry.volume()


def unit(vector):
    """Unit vector, or None if the input has no length."""
    length = sum(c * c for c in vector) ** 0.5
    if length < 1e-12:
        return None
    return [c / length for c in vector]


def add_body_force(session, model, bc, acceleration, direction, loading_type):
    """Apply an acceleration to every block, as a point load at its centroid.

    This is the tilted-table / static-seismic load: a rotated gravity. It is
    expressed as `mass * a * direction` per block rather than through
    `add_global_body_force`, so the solvers that read point loads pick it up
    with no compas_dem change.

    Note gravity itself is applied by the solver (from the block densities), so
    a BodyForce should carry only the ADDED component — for a tilt of angle t,
    a horizontal `a = g * tan(t)`, or a seismic coefficient `a = k * g`.
    """
    unit_direction = unit(direction)
    if unit_direction is None:
        warn("The direction vector has zero length.")
        return False

    added, skipped = 0, []
    for block in model.elements():
        mass = block_mass(block)
        if mass is None:
            skipped.append(block.graphnode)
            continue
        force = [mass * acceleration * c for c in unit_direction]
        bc.add_point_load(block_index=block.graphnode, force=force, loading_type=loading_type)
        added += 1

    if not added:
        warn("No block has a material with a density, so no body force could be applied. Run Model_material and Model_materialassign first.")
        return False

    if skipped:
        shown = ", ".join(str(n) for n in skipped[:5])
        more = f" (+{len(skipped) - 5} more)" if len(skipped) > 5 else ""
        warn(f"Blocks {shown}{more} have no material density and were skipped.")

    print(f"Added a body force of {acceleration} m/s2 along {unit_direction} to {added} block(s), as centroid point loads.")
    print("  Gravity is applied by the solver itself, so this should be the ADDED component only (e.g. a = k*g).")
    return True


def add_load(session, model, bc, bc_kind="Mixed"):
    def is_(*kinds):
        return lambda v: v["kind"] in kinds

    # only offer what this BC's kind accepts, so a Displacements BC cannot be
    # given loads and a Loads BC cannot quietly acquire gravity
    load_types = []
    if session.bc_allows(bc_kind, "gravity"):
        load_types.append("Gravity")
    if session.bc_allows(bc_kind, "load"):
        load_types += ["Point", "Surface", "BodyForce"]
    if not load_types:
        warn(f"This is a {bc_kind} boundary condition, so it takes no loads. Use Problem_displacements, or change its kind in Problem_createbc.")
        return False

    options = Options("Add load")
    options.add_list("kind", load_types, keyword="LoadType")
    options.add_number("g", bc.g or 9.81, minimum=0.0, keyword="G", units="m/s2", prompt="Gravitational acceleration g", visible=is_("Gravity"))
    options.add_number("fx", 0.0, keyword="Fx", units="N", prompt="Force fx", visible=is_("Point", "Surface"))
    options.add_number("fy", 0.0, keyword="Fy", units="N", prompt="Force fy", visible=is_("Point", "Surface"))
    options.add_number("fz", -1000.0, keyword="Fz", units="N", prompt="Force fz", visible=is_("Point", "Surface"))
    # body force: a magnitude plus a direction, applied to every block by mass
    options.add_number("a", 1.0, minimum=0.0, keyword="Acceleration", units="m/s2", prompt="Acceleration magnitude", visible=is_("BodyForce"))
    options.add_number("ax", 1.0, keyword="Dx", prompt="Direction x", visible=is_("BodyForce"))
    options.add_number("ay", 0.0, keyword="Dy", prompt="Direction y", visible=is_("BodyForce"))
    options.add_number("az", 0.0, keyword="Dz", prompt="Direction z", visible=is_("BodyForce"))
    # time-series shape used by the solver, straight from BoundaryCondition.add_point_load
    options.add_toggle("loading", False, off="Ramp", on="Instantaneous", text=True, keyword="Loading", visible=is_("Point", "Surface", "BodyForce"))

    values = options.get()
    if values is None:
        return False

    kind = values["kind"]
    force = [values["fx"], values["fy"], values["fz"]]
    loading_type = values["loading"].lower()

    if kind == "Gravity":
        bc.add_gravity(values["g"])
        print(f"Gravity set to {values['g']} m/s2.")
        return True

    if kind == "BodyForce":
        return add_body_force(
            session,
            model,
            bc,
            values["a"],
            [values["ax"], values["ay"], values["az"]],
            loading_type,
        )

    if kind == "Point":
        nodes = selected_nodes(session, model, "Select blocks to load")
        if not nodes:
            return False
        for node in nodes:
            # no `point` and no `moment`: the force acts at the block centroid
            bc.add_point_load(block_index=node, force=force, loading_type=loading_type)
        print(f"Added {loading_type} point load {force} to {len(nodes)} block(s).")
        return True

    if kind == "Surface":
        nodes = selected_nodes(session, model, "Select ONE block for the surface load")
        if not nodes:
            return False
        node = nodes[0]
        block = model.graph.node_element(node)

        faces = pick_faces(block)
        if not faces:
            return False

        # add_surface_load takes a single face, so a multi-face selection is one
        # entry per face — each keeps its own area when the solver resolves it
        for face_index in faces:
            bc.add_surface_load(block_index=node, face_index=face_index, load=force, loading_type=loading_type)
        listed = ", ".join(str(f) for f in faces)
        print(f"Added {loading_type} surface load {force} on block {node}, face(s) {listed}.")
        return True

    return False


def remove_load(bc):
    kind = choose("Remove which load type", ["Gravity", "Point", "Surface", "AllPoint"])
    if kind is None:
        return False

    if kind == "Gravity":
        bc.add_gravity(0.0)
        print("Gravity cleared (g = 0).")
        return True

    if kind == "AllPoint":
        # A body force becomes one point load per block, so removing it one
        # entry at a time is unusable — this clears the whole set.
        entries = bc.point_loads
        if not entries:
            warn("No point loads to remove.")
            return False
        count = len(entries)
        entries[:] = []
        print(f"Removed all {count} point load(s), including any body force.")
        return True

    # the properties return the underlying lists, so popping edits the boundary condition
    entries = bc.point_loads if kind == "Point" else bc.surface_loads
    if not entries:
        warn(f"No {kind.lower()} loads to remove.")
        return False

    labels = [f"{i}: {e}" for i, e in enumerate(entries)]
    label = rs.ListBox(labels, message=f"{kind} load to remove", title="Loads")
    if not label:
        return False

    removed = entries.pop(int(label.split(":")[0]))
    print(f"Removed {kind.lower()} load: {removed}")
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

    if not problem.boundary_conditions:
        return warn(f"{name} has no boundary condition. Run Problem_createbc first — loads belong to a boundary condition.")

    picked = session.choose_bc(problem, message="Boundary condition to add the load to")
    if picked is None:
        return
    index, bc = picked

    bc_kind = session.bc_kind(name, index)
    print(f"{bc_name(bc, index)} is a {bc_kind} boundary condition.")

    option = choose("Loads", ["Add", "Remove"], default="Add")
    if option is None:
        return

    changed = add_load(session, model, bc, bc_kind) if option == "Add" else remove_load(bc)
    if not changed:
        return

    session.save_problems()
    session.draw_bc(name, bc, index, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
