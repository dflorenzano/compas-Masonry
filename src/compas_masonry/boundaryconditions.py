"""Display helpers for compas_dem boundary conditions.

The compas_dem API is called directly by the commands: `BoundaryCondition(name=...)`,
`bc.add_point_load(...)`, `problem.add_boundary_condition(bc)`,
`model.solve(problem, boundary_conditions=[...])`. What is left here is what
compas_dem does not do — naming boundary conditions for Rhino layers and pick
lists, and reading their entries for drawing.

Renamed from `loadcases.py`: compas_dem renamed `LoadCase` to `BoundaryCondition`
(`problem/boundary_condition.py`), so "BC" is the vocabulary everywhere now.

BC entries are sparse by design::

    add_displacement(block_index, dx=None, dy=1.0, dz=None)
        -> {"block_index": 0, "translation": [None, 1.0, None], "rotation": None}
    add_rotation(block_index, [0, 0, 0.1])
        -> {"block_index": 0, "translation": None, "rotation": [0, 0, 0.1]}

`None` means "this DOF is unconstrained", which is not the same as 0.0, so the
vector helpers below fill the gaps with 0.0 for drawing only.

"""

__all__ = [
    "bc_name",
    "bc_labels",
    "is_support",
    "entry_vector",
    "describe_entry",
]


def bc_name(bc, index) -> str:
    """Display name of a boundary condition: its own name, or "BC<n>".

    Reads the private `_name`, not `name`: compas `Data.name` falls back to the
    class name, so an unnamed BC reports "BoundaryCondition" and never reaches
    the "BC<n>" default. `_name` is None until something sets a real name.
    """
    name = getattr(bc, "_name", None) or getattr(bc, "name", None)
    if not name or name == type(bc).__name__:
        return f"BC{index + 1}"
    return name


def bc_labels(problem) -> list:
    """Index-prefixed labels for every boundary condition, for printing and picking."""
    return [f"{i}: {bc_name(bc, i)}" for i, bc in enumerate(problem.boundary_conditions)]


def is_support(entry) -> bool:
    """True if a displacement entry is a fixed support (all DOFs zero).

    Supports live on the Problem and are copied into every boundary condition by
    `Problem.add_boundary_condition`, so they show up among the displacements and
    must be filtered out of anything that edits *prescribed* BCs.
    """
    return entry.get("translation") == [0.0, 0.0, 0.0] and entry.get("rotation") == [0.0, 0.0, 0.0]


def entry_vector(entry, key) -> list:
    """The "translation" or "rotation" of an entry as a drawable [x, y, z].

    Unconstrained components (None) and a missing vector become 0.0 — good
    enough to draw, never written back to the boundary condition.
    """
    vector = entry.get(key)
    if not vector:
        return [0.0, 0.0, 0.0]
    return [0.0 if v is None else float(v) for v in vector]


def describe_entry(entry) -> str:
    """One-line description of a displacement entry, for pick lists.

    Keeps the None components visible ("free"), since that is the difference
    between a prescribed zero and an unconstrained DOF.
    """

    def fmt(vector):
        if not vector:
            return "-"
        return "[" + ", ".join("free" if v is None else f"{v:g}" for v in vector) + "]"

    return f"block {entry.get('block_index')} translation={fmt(entry.get('translation'))} rotation={fmt(entry.get('rotation'))}"
