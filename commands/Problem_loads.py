#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_loads — apply/remove loads on a Problem: gravity / point / surface.

Flow: pick a problem -> Add / Remove -> Gravity / Point / Surface.
- Gravity   : one acceleration value applied to all blocks (problem.add_gravity).
- Point     : select blocks, give a force vector [fx,fy,fz] (problem.add_point_load per block).
- Surface   : select one block + face index, give a load vector (problem.add_surface_load).

The Problem is the source of truth; after any change session.draw_problem()
clears and regenerates the Rhino geometry under the problem's Loads layers, each
object tagged back to the block it refers to (element_guid + bc_index).
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def selected_nodes(session, model, message):
    """Select Rhino block objects and resolve them to graph node indices."""
    guids = compas_rhino.objects.select_objects(message=message)
    if not guids:
        return []
    guid_element_map = session.guid_element_map(model)
    return sorted({n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None})


def get_force(prompt="Force"):
    fx = rs.GetReal(f"{prompt} fx [N]", 0.0)
    if fx is None:
        return None
    fy = rs.GetReal(f"{prompt} fy [N]", 0.0)
    if fy is None:
        return None
    fz = rs.GetReal(f"{prompt} fz [N]", -1000.0)
    if fz is None:
        return None
    return [fx, fy, fz]


def add_loads(session, problem, model):
    kind = rs.GetString(message="Load type", strings=["Gravity", "Point", "Surface"])
    if not kind:
        return

    if kind == "Gravity":
        g = rs.GetReal("Gravitational acceleration g [m/s2]", problem.boundary_conditions.g or 9.81, 0.0)
        if g is None:
            return
        problem.add_gravity(g)
        print(f"Gravity set to {g} m/s2.")

    elif kind == "Point":
        nodes = selected_nodes(session, model, "Select blocks to load")
        if not nodes:
            return
        force = get_force("Point load")
        if force is None:
            return
        for node in nodes:
            problem.add_point_load(node, force)
        print(f"Added point load {force} to {len(nodes)} block(s).")

    elif kind == "Surface":
        nodes = selected_nodes(session, model, "Select ONE block for the surface load")
        if not nodes:
            return
        node = nodes[0]
        block = model.graph.node_element(node)
        nfaces = block.modelgeometry.number_of_faces()
        face_index = rs.GetInteger(f"Face index (0..{nfaces - 1})", 0, 0, nfaces - 1)
        if face_index is None:
            return
        load = get_force("Surface load")
        if load is None:
            return
        problem.add_surface_load(node, face_index, load)
        print(f"Added surface load {load} on block {node}, face {face_index}.")


def remove_loads(problem):
    kind = rs.GetString(message="Remove which load type", strings=["Gravity", "Point", "Surface"])
    if not kind:
        return
    bc = problem.boundary_conditions

    if kind == "Gravity":
        bc.add_gravity(0.0)
        print("Gravity cleared (g = 0).")
        return

    entries = bc.point_loads if kind == "Point" else bc.surface_loads
    if not entries:
        return warn(f"No {kind.lower()} loads to remove.")
    for i, e in enumerate(entries):
        print(f"{i}: {e}")
    idx = rs.GetString(message=f"{kind} load index to remove", strings=[str(i) for i in range(len(entries))])
    if not idx:
        return
    removed = entries.pop(int(idx))
    print(f"Removed {kind.lower()} load: {removed}")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to edit loads on")
    if name is None:
        return
    problem = session.problems[name]

    option = rs.GetString(message="Loads", strings=["Add", "Remove"])
    if not option:
        return

    if option == "Add":
        add_loads(session, problem, model)
    elif option == "Remove":
        remove_loads(problem)

    session.save_problems()
    session.draw_problem(name, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
