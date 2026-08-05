"""Display helpers for compas_dem boundary conditions.

A boundary condition is a **typed object** since the 2026-08 restructure: either a
`Load` (`PointLoad`, `Moment`, `SurfaceLoad`, `BodyForce`) or a `Displacement`
(`Translation`, `Rotation`). The class carries the meaning, so there is no longer
a session-side "kind" to track and no named BC container to manage — **a Problem
IS the load case.**

What is left here is what compas_dem does not do: describing a boundary condition
for a Rhino pick list, and resolving where it applies so it can be drawn.

Two things a caller has to keep straight:

- **A displacement component of `None` means "unconstrained"**, which is not the
  same as a prescribed 0.0. `components()` fills the gaps with 0.0 so a vector can
  be drawn; `describe()` keeps them visible as "free". Never write the filled
  vector back.
- **A `PointLoad` carries an anchor**, not a point: `("vertex", i)`, `("face", i)`,
  `("point", [x, y, z])` or `("centroid", None)`. `anchor_point()` turns that into
  coordinates against the block's geometry.

Boundary conditions are **grouped for display by their own `name`**. compas_dem has
no container to group them — a Problem holds one flat list — but every boundary
condition is a compas `Data`, and `name` survives a JSON round trip even though it
is not part of `__data__`. So the name IS the group: every condition called
"Load_1" is drawn on the layer `…::BoundaryConditions::Load_1`, and adding a load
either extends an existing group or starts a new one.

That keeps the grouping where it belongs — on the objects, serialized with them —
rather than in a session-side map keyed by list index, which is exactly what the
old BC-kind map was and why it needed reindexing on every delete.

"""

__all__ = [
    "is_load",
    "is_displacement",
    "group_name",
    "groups",
    "group_names",
    "next_group_name",
    "bc_label",
    "bc_labels",
    "describe",
    "components",
    "anchor_point",
    "block_index",
]

# Default group-name stems, per kind.
LOAD_STEM = "Load"
DISPLACEMENT_STEM = "Displacement"


def _classname(bc) -> str:
    return type(bc).__name__


def is_load(bc) -> bool:
    """True if the boundary condition is a Load (as opposed to a Displacement)."""
    from compas_dem.problem import Load

    return isinstance(bc, Load)


def is_displacement(bc) -> bool:
    """True if the boundary condition is a prescribed movement."""
    from compas_dem.problem import Displacement

    return isinstance(bc, Displacement)


def block_index(bc):
    """The block a boundary condition applies to, or None for a global one.

    `BodyForce` applies to every block, so it has no `block`.
    """
    return getattr(bc, "block", None)


def group_name(bc) -> str:
    """The display group a boundary condition belongs to.

    Reads the private `_name`, not `name`: compas `Data.name` falls back to the
    CLASS NAME when nothing was set, so an unnamed `PointLoad` reports
    "PointLoad" and would silently become its own group. `_name` is None until
    something sets a real name, which is the honest signal.

    An unnamed condition falls into the default group for its kind, so a session
    written before grouping existed still draws somewhere sensible.
    """
    name = getattr(bc, "_name", None)
    if name:
        return name
    return f"{LOAD_STEM}_1" if is_load(bc) else f"{DISPLACEMENT_STEM}_1"


def groups(problem, kind=None) -> dict:
    """The boundary conditions of a problem, grouped by name, in insertion order.

    Parameters
    ----------
    problem : :class:`compas_dem.problem.Problem`
    kind : str, optional
        "load" or "displacement" to restrict the result to one kind. Groups are
        per-kind by construction, since the two use different name stems.

    Returns
    -------
    dict[str, list]
        {group name: [boundary conditions]}.

    """
    if kind == "load":
        conditions = problem.loads
    elif kind == "displacement":
        conditions = problem.displacements
    else:
        conditions = problem.boundary_conditions

    grouped = {}
    for bc in conditions:
        grouped.setdefault(group_name(bc), []).append(bc)
    return grouped


def group_names(problem, kind=None) -> list:
    """The existing group names of a problem, in insertion order."""
    return list(groups(problem, kind))


def next_group_name(problem, kind) -> str:
    """The next free default group name: "Load_3", "Displacement_2".

    Counts up past whatever exists rather than using len(), so deleting a middle
    group never produces a name that is already taken.
    """
    stem = LOAD_STEM if kind == "load" else DISPLACEMENT_STEM
    # a name may be reused across kinds, so check every group, not just this kind
    taken = set(group_names(problem))
    i = 1
    while f"{stem}_{i}" in taken:
        i += 1
    return f"{stem}_{i}"


def bc_label(bc, index) -> str:
    """Index-prefixed one-line label: "0: [Load_1] PointLoad on block 4 …"."""
    return f"{index}: [{group_name(bc)}] {describe(bc)}"


def bc_labels(problem) -> list:
    """Labels for every boundary condition on a problem, for printing and picking."""
    return [bc_label(bc, i) for i, bc in enumerate(problem.boundary_conditions)]


def _fmt(vector) -> str:
    """Format a vector, keeping unconstrained components visible as "free"."""
    if vector is None:
        return "-"
    return "[" + ", ".join("free" if v is None else f"{v:g}" for v in vector) + "]"


def describe(bc) -> str:
    """One-line description of any boundary condition, for pick lists and printing.

    Dispatches on the class rather than on stored data, because the class is now
    what carries the meaning.
    """
    kind = _classname(bc)

    if kind == "PointLoad":
        anchor = bc.anchor
        where = f"{anchor}" if bc.anchor_value is None else f"{anchor} {bc.anchor_value}"
        return f"PointLoad on block {bc.block} at {where}, force {_fmt(bc.force)}"

    if kind == "Moment":
        return f"Moment on block {bc.block}, {_fmt(bc.moment)}"

    if kind == "SurfaceLoad":
        return f"SurfaceLoad on block {bc.block} face {bc.face}, traction {_fmt(bc.traction)}"

    if kind == "BodyForce":
        return f"BodyForce on every block, acceleration {_fmt(bc.acceleration)}"

    if kind == "Translation":
        return f"Translation of block {bc.block}, {_fmt(bc.components)}"

    if kind == "Rotation":
        return f"Rotation of block {bc.block}, {_fmt(bc.components)}"

    return kind


def components(bc) -> list:
    """A displacement's components as a drawable [x, y, z].

    Unconstrained components (None) become 0.0 — good enough to draw, and never
    written back to the boundary condition.
    """
    raw = getattr(bc, "components", None)
    if not raw:
        return [0.0, 0.0, 0.0]
    return [0.0 if v is None else float(v) for v in raw]


def anchor_point(bc, block):
    """Resolve where a PointLoad applies, in world coordinates.

    A `PointLoad` stores an anchor (`vertex` / `face` / `point` / `centroid`) plus
    its value, not a resolved location — the same load survives a change of block
    geometry. Drawing needs the coordinates, so resolve them here.

    Returns
    -------
    list[float] or None
        The application point, or None if the anchor cannot be resolved against
        this block's geometry.

    """
    anchor = getattr(bc, "anchor", None)
    value = getattr(bc, "anchor_value", None)
    geometry = getattr(block, "modelgeometry", None)
    if geometry is None:
        return None

    try:
        if anchor == "point":
            return list(value)
        if anchor == "vertex":
            return list(geometry.vertex_point(value))
        if anchor == "face":
            return list(geometry.face_centroid(value))
        # "centroid", or anything unrecognised: fall back to the block centroid
        return list(geometry.centroid())
    except Exception:
        return None
