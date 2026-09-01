"""Display helpers for compas_dem boundary conditions.

compas_dem groups boundary conditions: a `Problem` holds a list of
`BoundaryConditionGroup`, and each group holds the typed objects that act
together — `PointLoad`, `SurfaceLoad`, `BodyForce` on the load side,
`Translation` and `Rotation` on the displacement side. The group is the unit the
solver applies, and its `name` is the unit the plugin draws: one Rhino layer per
group, at `…::BoundaryConditions::<group name>`.

That replaced this module's previous scheme, which faked grouping by reading each
condition's own `name` because a Problem held one flat list. Nothing here has to
invent grouping any more; what is left is describing a group or a condition for a
pick list, and resolving where it applies so it can be drawn.

**A group is single-kind by plugin convention, not by compas_dem.** A
`BoundaryConditionGroup` will happily hold loads and displacements at once.
Problem_loads and Problem_displacements each offer only the groups of their own
kind, so the two never meet — but that rule lives in those two commands and in
`group_kind` below, nowhere else. A group built from a script can hold both, and
everything here still works on it; it will simply be offered in one command and
drawn in one layer.

Two things a caller has to keep straight:

- **A displacement component of `None` means "unconstrained"**, which is not the
  same as a prescribed 0.0. `components()` fills the gaps with 0.0 so a vector can
  be drawn; `describe()` keeps them visible as "free". Never write the filled
  vector back.
- **A moment is a `PointLoad`**, not a class of its own: `add_moment` builds one
  with a zero force vector and a `moment`. `is_moment()` is what tells them apart,
  and it is why `describe` cannot dispatch on the class name alone.

**On the compas_dem names.** `compas_dem.problem` exports `Load`, `Translation` and
`Rotation`, and the last two collide with `compas.geometry.Translation` and
`compas.geometry.Rotation` — a script doing a star-import of both packages gets
whichever came last. Nothing in this plugin binds those bare names: they are
imported here under `Applied…`/`Prescribed…` aliases, and everywhere else the type
is matched as a STRING through `_classname(bc)`.

Those strings are compas_dem class names, not labels this plugin is free to choose.
Renaming what the user sees means adding a display-name map, because the same
strings are the stored discriminator — and renaming the classes themselves means
changing compas_dem, which also changes the `dtype` in every serialized session.
Neither is done here.
"""

__all__ = [
    "LOAD_STEM",
    "DISPLACEMENT_STEM",
    "is_load",
    "is_displacement",
    "is_moment",
    "loads_of",
    "conditions_of",
    "group_kind",
    "groups_of_kind",
    "group_names",
    "next_group_name",
    "group_label",
    "group_labels",
    "bc_label",
    "bc_labels",
    "describe",
    "components",
    "block_index",
    "load_point",
    "remove_condition",
    "remove_group",
]

# Default group-name stems, per kind. Purely cosmetic — they seed the name the
# command suggests and nothing reads meaning back out of them. `group_kind` looks
# at what a group HOLDS, never at what it is called.
LOAD_STEM = "Load"
DISPLACEMENT_STEM = "Displacement"


def _classname(bc) -> str:
    return type(bc).__name__


def is_load(bc) -> bool:
    """True if the boundary condition is a load (as opposed to a displacement)."""
    from compas_dem.problem import Load as AppliedLoad

    return isinstance(bc, AppliedLoad)


def is_displacement(bc) -> bool:
    """True if the boundary condition is a prescribed movement."""
    from compas_dem.problem import Displacement as PrescribedDisplacement

    return isinstance(bc, PrescribedDisplacement)


def is_moment(bc) -> bool:
    """True if a PointLoad is really a moment: a couple with no net force.

    `BoundaryConditionGroup.add_moment` stores a `PointLoad` with
    `force=[0, 0, 0]` and a `moment`, so the class does not distinguish the two
    and both the description and the drawing have to.
    """
    if _classname(bc) != "PointLoad":
        return False
    return not any(bc.force or []) and any(bc.moment or [])


def block_index(bc):
    """The block a boundary condition applies to, or None for a global one.

    `BodyForce` applies to every block, so it has no block index.
    """
    return getattr(bc, "block_index", None)


# =============================================================================
# Groups
# =============================================================================


def loads_of(group) -> list:
    """Every load in a group: body forces, then point loads, then surface loads."""
    return list(group.body_forces) + list(group.point_loads) + list(group.surface_loads)


def conditions_of(group) -> list:
    """Every boundary condition in a group, loads first."""
    return loads_of(group) + list(group.displacements)


def group_kind(group):
    """ "load", "displacement", or None for an empty group.

    Decided by CONTENT, so a group is whatever it actually holds — never by its
    name. compas_dem attaches no meaning to a group's name, so reading a kind out
    of "Load_1" would be inventing information, and it goes wrong the moment a
    custom-named group is emptied: "Settlement" would come back as a load group
    and move to the other command's picker without a word.

    An empty group therefore has NO kind, and `groups_of_kind` offers it to both
    commands. Whichever writes to it first decides what it is.

    A mixed group (possible from a script, never from the commands) reports
    "displacement", so it stays out of the load pickers rather than growing.
    """
    if group.displacements:
        return "displacement"
    if loads_of(group):
        return "load"
    return None


def groups_of_kind(problem, kind=None) -> list:
    """The problem's groups, optionally restricted to one kind.

    **Empty groups are included in every kind**, because they have none yet
    (`group_kind`). That is what lets a group emptied by Remove > One still be
    refilled from the command it was created in — and deleted from either.
    """
    groups = list(problem.boundary_conditions)
    if kind is None:
        return groups
    return [group for group in groups if group_kind(group) in (kind, None)]


def group_names(problem, kind=None) -> list:
    """The names of a problem's groups, in registration order."""
    return [group.name for group in groups_of_kind(problem, kind)]


def next_group_name(problem, kind) -> str:
    """The next free default group name: "Load_3", "Displacement_2".

    Counts up past whatever exists rather than using len(), so deleting a middle
    group never produces a name that is already taken. Checks EVERY group, not
    just this kind: `Problem.add_boundary_condition` raises on a duplicate name
    regardless of what the group holds.
    """
    stem = LOAD_STEM if kind == "load" else DISPLACEMENT_STEM
    taken = set(group_names(problem))
    i = 1
    while f"{stem}_{i}" in taken:
        i += 1
    return f"{stem}_{i}"


def group_label(group) -> str:
    """One-line summary of a group: "Load_1 — 2 loads"."""
    counts = []
    if loads_of(group):
        n = len(loads_of(group))
        counts.append(f"{n} load{'s' if n != 1 else ''}")
    if group.displacements:
        n = len(group.displacements)
        counts.append(f"{n} movement{'s' if n != 1 else ''}")
    return f"{group.name} — {', '.join(counts) or 'empty'}"


def group_labels(problem, kind=None) -> list:
    """Index-prefixed labels for a problem's groups, for printing and picking."""
    return [f"{i}: {group_label(group)}" for i, group in enumerate(groups_of_kind(problem, kind))]


# =============================================================================
# Individual conditions
# =============================================================================


def bc_label(bc, index) -> str:
    """Index-prefixed one-line label: "0: PointLoad on block 4 …"."""
    return f"{index}: {describe(bc)}"


def bc_labels(group) -> list:
    """Labels for every condition in a group, for printing and picking."""
    return [bc_label(bc, i) for i, bc in enumerate(conditions_of(group))]


def _fmt(vector) -> str:
    """Format a vector, keeping unconstrained components visible as "free"."""
    if vector is None:
        return "-"
    return "[" + ", ".join("free" if v is None else f"{v:g}" for v in vector) + "]"


def describe(bc) -> str:
    """One-line description of any boundary condition, for pick lists and printing."""
    kind = _classname(bc)

    if kind == "PointLoad":
        if is_moment(bc):
            return f"Moment on block {bc.block_index}, {_fmt(bc.moment)}"
        where = f" at {[round(c, 3) for c in bc.point]}" if bc.point else " at the centroid"
        return f"PointLoad on block {bc.block_index}{where}, force {_fmt(bc.force)}"

    if kind == "SurfaceLoad":
        return f"SurfaceLoad on block {bc.block_index} face {bc.face_index}, load {_fmt(bc.load)}"

    if kind == "BodyForce":
        return f"BodyForce on every block, acceleration {_fmt(bc.acceleration)}"

    if kind == "Gravity":
        return f"Gravity, g = {bc.g:g}"

    if kind == "Translation":
        return f"Translation of block {bc.block_index}, {_fmt(bc.translation)}"

    if kind == "Rotation":
        return f"Rotation of block {bc.block_index}, {_fmt(bc.rotation)}"

    return kind


def components(bc) -> list:
    """A displacement's components as a drawable [x, y, z].

    Reads `translation` or `rotation` — the two carry different attribute names,
    and neither is called `components` any more. Unconstrained entries (None)
    become 0.0: good enough to draw, and never written back.
    """
    raw = getattr(bc, "translation", None)
    if raw is None:
        raw = getattr(bc, "rotation", None)
    if not raw:
        return [0.0, 0.0, 0.0]
    return [0.0 if v is None else float(v) for v in raw]


def load_point(bc, block):
    """Where a PointLoad applies, in world coordinates.

    A `PointLoad` now carries a resolved `point`, because the vertex/face anchor
    is resolved by `Problem.add_point_load_at_vertex` / `_at_face` when the load
    is built. `point` is None for a load applied at the centroid, which is what
    the fallback covers.

    Returns
    -------
    list[float] or None
        The application point, or None if it cannot be resolved against this
        block's geometry.
    """
    point = getattr(bc, "point", None)
    if point:
        return list(point)

    geometry = getattr(block, "modelgeometry", None)
    if geometry is None:
        return None
    try:
        return list(geometry.centroid())
    except Exception:
        return None


# =============================================================================
# Removal
# =============================================================================


def remove_condition(group, bc) -> bool:
    """Remove one boundary condition from its group.

    compas_dem exposes `add_*` but no remove, so this goes through the list
    properties — which return the LIVE lists (`group.point_loads is
    group._point_loads`), so removing through them mutates the group.

    That is the whole mechanism, and it would break QUIETLY if those properties
    ever started returning a copy: the call would succeed and the condition would
    still be there. Hence the check afterwards.

    Returns
    -------
    bool
        True if it was removed. Raises if the removal did not take effect.
    """
    for holder in (group.body_forces, group.point_loads, group.surface_loads, group.displacements):
        if bc in holder:
            holder.remove(bc)
            if bc in holder:
                raise RuntimeError(
                    "Removing a boundary condition had no effect — compas_dem's group properties no longer return the live list, so this needs a different mechanism."
                )
            return True
    return False


def remove_group(problem, group) -> bool:
    """Remove a whole group from a problem.

    Same mechanism and same caveat as `remove_condition`:
    `problem.boundary_conditions is problem._boundary_conditions`.
    """
    groups = problem.boundary_conditions
    if group not in groups:
        return False
    groups.remove(group)
    if group in groups:
        raise RuntimeError(
            "Removing a boundary condition group had no effect — `Problem.boundary_conditions` no longer returns the live list, so this needs a different mechanism."
        )
    return True
