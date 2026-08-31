"""Reading a compas_dem `Results` — the derived quantities, without Rhino.

`Results` stores raw per-node and per-edge attributes; every number an engineer
actually asks for (stress, opening, reaction, displacement) has to be derived
from those. This module does that derivation and nothing else: no Rhino, no
session, so it is testable headlessly and shared by the drawing code in
`session.py` and by the reporting commands.

The derivations follow a tested reference viewer for the sibling `masonry_dem`
package (see `temp/wiki_plugin_guide.md` §7), remapped to this `Results` API —
notably `resultant_global(edge)`, where the reference has `force(edge)`.

What each solver fills in differs, so every helper tolerates missing data and
simply returns less:

- **CRA / RBE** write contact forces on the edges and an *identity*
  transformation per block. Stresses, openings and reactions are available;
  displacements are all zero.
- **LMGC90** writes real transformations, so displacements are meaningful.
"""

__all__ = [
    "contact_resultants",
    "application_point_report",
    "face_stresses",
    "contact_openings",
    "tension_contacts",
    "tension_report",
    "block_displacements",
    "support_reactions",
    "summary",
    "CSV_HEADER",
    "block_result_rows",
    "FORCE_UNIT",
    "STRESS_UNIT",
    "to_force_unit",
    "to_stress_unit",
]

# DISPLAY UNITS. The solvers work in newtons and every stored value stays in
# newtons — only what a human reads is converted. The conversion lives here, in
# the one module both the reports and the Rhino drawing derive their numbers
# from, so a table, an exported row and a reaction tag cannot disagree about a
# force the way they did while the tag divided by 1000 on its own.
#
# Stress is `|F . n| / area`, so newtons over square metres: the same factor
# takes Pa to kPa, and kN/m2 IS kPa. The two constants are therefore one
# conversion, not two that happen to match.
#
# ASSUMES A MODEL IN METRES. Nothing here can detect the document's unit, so a
# model drawn in millimetres reports forces that are correct and areas that are
# not, which shows up as stress wrong by 10^6. That was true of the kN tag
# before this and is unchanged by it — it is simply now written down.
FORCE_UNIT = "kN"
STRESS_UNIT = "kPa"
_PER_KILO = 1e-3


def to_force_unit(value):
    """N -> kN. `None` passes through: a force the solver never produced is not 0."""
    return None if value is None else value * _PER_KILO


def to_stress_unit(value):
    """Pa -> kPa, i.e. kN/m2. `None` passes through."""
    return None if value is None else value * _PER_KILO


# One row per (block, contact), with the block's displacement repeated on every
# row of that block. Flat and redundant on purpose: it pivots in a spreadsheet
# without anyone having to carry a value down a merged cell.
#
# The unit is in the column NAME rather than in a legend somewhere, because a
# bare "F_magnitude" is what let the tags say kN while these rows said N.
CSV_HEADER = [
    "block",
    "with",
    f"F_magnitude_{FORCE_UNIT}",
    f"Fx_{FORCE_UNIT}",
    f"Fy_{FORCE_UNIT}",
    f"Fz_{FORCE_UNIT}",
    f"stress_{STRESS_UNIT}",
    "opening",
    "u_magnitude",
    "ux",
    "uy",
    "uz",
]


def _magnitude(vector) -> float:
    return sum(c * c for c in vector) ** 0.5


def _edge_label(edge) -> str:
    return f"{edge[0]}-{edge[1]}"


def contact_normal(results, edge):
    """The contact normal, or None.

    `contact_frame` is the obvious source, but **CRA and RBE never write one**:
    `_post_processing_cra` stores the polygon, the points, the resultants and
    the magnitude, and nothing else. Requiring a frame silently emptied stress
    and reactions for every CRA/RBE result, so the polygon's own normal is used
    when there is no frame.

    TRAP — do not "fix" this by reading `contact_data.frame`. The frame is not
    actually missing under CRA: `cra.py` builds the FrictionContact WITH
    `frame=interface.frame` and simply never calls
    `set_edge(edge, "contact_frame", ...)`. So a frame is reachable at
    `contact_data.frame`, and it is ANTI-PARALLEL to the polygon normal on every
    contact — measured on a 15-block arch, `frame.zaxis . polygon.normal == -1.000`
    on all 14 contacts, not some of them.

    Nothing downstream is neutral about that flip:

    - `face_stresses` uses `|F . n|`, so it does not care.
    - `support_reactions` picks its sign from `offset . normal`. With the POLYGON
      normal it produces the correct upward reaction (-10.881, 0, +25.852) N.
      Swap in `frame.zaxis` and every CRA reaction inverts to (+10.881, 0, -25.852)
      — pointing down and out of the abutment, which is wrong and which no test
      would catch, because the magnitude is identical.

    So the current behaviour is right and the reasoning under it is not: the
    `support_reactions` docstring claims "the contact normal points u -> v", and
    that is not the convention CRA is actually storing. Before touching either
    function, settle what CRA's normal orientation really is (upstream, against
    `interface.frame`), then make BOTH agree. The compas_dem viewer sidesteps the
    question entirely by resolving reaction direction geometrically — flipping
    the resultant to point away from the support centroid — and never reads a
    stored normal at all. That is the more robust convention if this is reworked.
    """
    frame = results.contact_frame(edge)
    if frame is not None:
        return list(frame.zaxis)

    polygon = results.contact_polygon(edge)
    if polygon is None:
        return None
    try:
        return list(polygon.normal)
    except Exception:
        return None


def contact_point(results, edge):
    """A representative point on the contact, or None. Frame origin, else the
    polygon centroid, else the first stored contact point."""
    frame = results.contact_frame(edge)
    if frame is not None:
        return list(frame.point)

    polygon = results.contact_polygon(edge)
    if polygon is not None:
        return list(polygon.centroid)

    points = results.contact_point(edge)
    if points:
        return list(points[0])
    return None


def contact_resultants(results) -> list:
    """[(point, vector, magnitude, edge), …] for every contact carrying a force.

    The application point is where the force actually acts on the joint, which
    is what makes the drawn resultants a line of thrust rather than a chain of
    joint midpoints. Order: `force_point` when the solver wrote one, else the
    contact's own `resultantpoint` (the normal-force-weighted point — the only
    source CRA/RBE fill in), else the contact frame origin, else the polygon
    centroid. CRA writes neither `force_point` nor a contact frame, so without
    the `resultantpoint` step every force lands on the joint centroid and the
    eccentricity — the whole answer — is thrown away.
    """
    out = []
    for edge in results.edges():
        vector = results.resultant_global(edge)
        if not vector:
            continue

        magnitude = results.force_magnitude(edge)
        if magnitude is None:
            magnitude = _magnitude(vector)
        if not magnitude:
            continue

        point = results.force_point(edge)
        if point is None:
            contact = results.contact_data(edge)
            resultantpoint = getattr(contact, "resultantpoint", None)
            point = None if resultantpoint is None else list(resultantpoint)
        if point is None:
            frame = results.contact_frame(edge)
            if frame is not None:
                point = list(frame.point)
            else:
                polygon = results.contact_polygon(edge)
                if polygon is None:
                    continue
                point = list(polygon.centroid)

        out.append((list(point), list(vector), float(magnitude), edge))
    return out


def application_points(results) -> tuple:
    """`(solved, centroid, dropped)` — how each contact's application point was found.

    The point a resultant is drawn at is the answer, not decoration: the offset of
    the thrust from the joint centre IS the eccentricity, and an arch whose
    resultants all sit on the joint midpoints is reporting its own geometry back.
    So it matters which of the four sources in `contact_resultants` supplied it.

    - `solved`   — `force_point` or the contact's `resultantpoint`. Trustworthy.
    - `centroid` — the polygon centroid or a contact frame origin. A *position on
      the joint*, unrelated to where the force acts. Eccentricity is lost, and so
      is every quantity derived from it.
    - `dropped`  — nothing at all, so `contact_resultants` skips the contact even
      though it carries a force. Missing from the drawing AND from every report.

    Returns three lists of edge labels. Kept out of `contact_resultants` so that
    function keeps its 4-tuple shape and its four call sites stay unchanged.
    """
    solved, centroid, dropped = [], [], []
    for edge in results.edges():
        if not results.resultant_global(edge):
            continue
        label = _edge_label(edge)
        if results.force_point(edge) is not None:
            solved.append(label)
            continue
        contact = results.contact_data(edge)
        if getattr(contact, "resultantpoint", None) is not None:
            solved.append(label)
        elif results.contact_frame(edge) is not None or results.contact_polygon(edge) is not None:
            centroid.append(label)
        else:
            dropped.append(label)
    return solved, centroid, dropped


def application_point_report(results):
    """A message naming the contacts whose application point is not a solved one, or None.

    Worded once here because two commands say it — Results_show as it draws and
    Results_print as it tabulates — and the same finding phrased two ways reads as
    two findings. Same reason and same shape as `tension_report`.

    Nothing is returned when every contact has a solved point, which is the normal
    case for CRA, RBE, LMGC90, PRD and BLA: all of them store a `contact_data`, and
    every compas_dem contact class answers `resultantpoint`.
    """
    _, centroid, dropped = application_points(results)
    if not centroid and not dropped:
        return None

    def where(labels):
        shown = ", ".join(labels[:5])
        return shown + (f", … (+{len(labels) - 5})" if len(labels) > 5 else "")

    parts = []
    if centroid:
        parts.append(
            f"{len(centroid)} contact(s) fall back to the joint centroid [{where(centroid)}] — "
            "their eccentricity is lost, so the thrust line, the stress distribution "
            "and any moment read off them are wrong."
        )
    if dropped:
        parts.append(
            f"{len(dropped)} contact(s) carry a force but have no application point at all "
            f"[{where(dropped)}] — they are missing from the drawing and from every report. "
            "A 3DEC edge with more than one subcontact does this."
        )
    return " ".join(parts)


def face_stresses(results) -> list:
    """[(sigma, point, label), …] — normal contact pressure per FACE contact.

    `|F . n| / polygon area`, where n is the contact frame's z-axis. Only face
    contacts have an area, so edge and point contacts are skipped rather than
    reported as infinite stress.
    """
    out = []
    for edge in results.edges():
        if not results.face_contact(edge):
            continue
        polygon = results.contact_polygon(edge)
        force = results.resultant_global(edge)
        normal = contact_normal(results, edge)
        if polygon is None or normal is None or not force:
            continue
        area = polygon.area
        if area <= 0:
            continue
        sigma = abs(sum(f * n for f, n in zip(force, normal))) / area
        out.append((sigma, contact_point(results, edge), _edge_label(edge)))
    return out


def contact_openings(results, tolerance=1e-9) -> list:
    """[(opening, point, label), …] — the largest POSITIVE gap per contact.

    A positive gap means the joint is open there. Contacts in compression
    everywhere (all gaps <= 0) are omitted, so the list is the set of open
    joints rather than every contact.
    """
    out = []
    for edge in results.edges():
        gaps = results.gap(edge)
        if not gaps:
            continue  # CRA/RBE write no gaps, so their results report none
        point = contact_point(results, edge)
        if point is None:
            continue
        opening = max(gaps)
        if opening > tolerance:
            out.append((float(opening), point, _edge_label(edge)))
    return out


def tension_report(results):
    """`(expected, message)` describing the tension in a result, or None if there is none.

    Formatting lives here rather than in the commands because two of them say it —
    Problem_solve at the moment the result is produced, Results_show when it is
    drawn — and a warning that is worded differently in the two places reads as two
    different findings.

    `expected` is True for a CRA penalty solve, which permits tension by design.
    The caller uses it to choose `print` over `warn`: the same numbers are a
    result there and a fault everywhere else.
    """
    contacts = tension_contacts(results)
    if not contacts:
        return None

    corners = sum(n for _, n, _ in contacts)
    largest = max(t for _, _, t in contacts)
    where = ", ".join(label for label, _, _ in contacts[:5])
    if len(contacts) > 5:
        where += f", … (+{len(contacts) - 5})"

    head = f"{len(contacts)} contact(s) carry tension at {corners} corner(s), max {largest:.4g} [{where}]."
    if results.metadata.get("penalty"):
        return True, f"{head} Expected: this is a CRA penalty solve, which permits tension instead of excluding it."
    return False, f"{head} A no-tension solve should not produce this — check the supports and the contact model."


def block_result_rows(report) -> list:
    """`CSV_HEADER`-shaped rows for one block report from `Results_block`.

    Takes the dict that command's `block_report` already builds — node,
    displacement, sorted contacts, force total — so the printed table and the
    exported file cannot disagree about a number.

    A block with no force-carrying contact still gets one row, with the contact
    columns blank. Dropping it would make a block that was selected and reported
    on vanish from the export, which reads as an export bug rather than as the
    finding it is.

    Missing values are written as empty cells rather than as 0: a stress of 0 and
    a stress the solver never produced are different answers, and `None` printed
    into a CSV becomes the literal string "None".
    """
    node = report["node"]
    displacement = report["displacement"]
    if displacement is None:
        u = ["", "", "", ""]
    else:
        magnitude, translation, _ = displacement
        u = [magnitude, translation[0], translation[1], translation[2]]

    def cell(value):
        return "" if value is None else value

    if not report["contacts"]:
        return [[node, "", "", "", "", "", "", ""] + u]

    rows = []
    # The report carries newtons, as everything stored does; the row is what a
    # person reads, so it is converted here and the column names say so.
    for contact in report["contacts"]:
        force = contact["force"]
        rows.append(
            [
                node,
                contact["with"],
                to_force_unit(contact["magnitude"]),
                to_force_unit(force[0]),
                to_force_unit(force[1]),
                to_force_unit(force[2]),
                cell(to_stress_unit(contact["stress"])),
                cell(contact["opening"]),
            ]
            + u
        )
    return rows


def tension_contacts(results, tolerance=1e-9) -> list:
    """[(label, n_corners, max_tension), …] — one per contact carrying tension.

    Masonry does not take tension, so a plain CRA or RBE solve is formulated to
    forbid it and any result here means the answer is not one the model can
    physically deliver. A CRA *penalty* solve deliberately permits it, penalising
    it instead of excluding it, so there the list is the answer rather than a
    fault — `results.metadata["penalty"]` is what tells the two apart, and the
    caller reports accordingly.

    Read per CORNER, not per resultant: a contact whose resultant is net
    compressive can still be in tension at some of its polygon vertices, and the
    resultant hides exactly that. `FrictionContact.tensiondata` is the stored
    per-corner answer, `[x, y, z, nx, ny, nz, 0.5 * force]` with a negative force,
    so nothing is recomputed here.

    Contacts with no per-corner forces are skipped rather than assumed sound.
    LMGC90 stores an `EdgeContact` or a `VertexContact` for degenerate contacts,
    and neither carries corner forces at all.
    """
    out = []
    # A 3DEC-to-DEM conversion may preserve an exterior resultant point by
    # distributing it to polygon vertices with affine (therefore sometimes
    # negative) weights. Those equivalent vertex values preserve force and
    # moment but are not native subcontact tension. 3DEC stores its actual
    # normal subcontact forces separately, positive in compression, so use
    # those for the mechanical state check.
    #
    # This branch was DISARMED until 2026-08-31: no backend wrote
    # `metadata["solver"]`, so it never ran and 3DEC results silently took the
    # generic path below — the exact over-reporting it exists to prevent.
    # `CM_Problem_solve.solve()` now stamps the solver name onto the results, so
    # it fires. NOT YET SEEN ON A REAL 3DEC RUN (3DEC is Windows-only and
    # licensed); if 3DEC tension reporting looks wrong, start here.
    if results.metadata.get("solver") == "3DEC":
        for edge in results.edges():
            tensions = [abs(float(value)) for value in (results.force_normal(edge) or []) if float(value) < -tolerance]
            if tensions:
                out.append((_edge_label(edge), len(tensions), max(tensions)))
        return out

    for edge in results.edges():
        contact = results.contact_data(edge)
        if contact is None:
            continue
        entries = getattr(contact, "tensiondata", None) or []
        # the halving in tensiondata is undone so the number matches a force
        tensions = [abs(entry[6]) * 2.0 for entry in entries]
        tensions = [t for t in tensions if t > tolerance]
        if tensions:
            out.append((_edge_label(edge), len(tensions), max(tensions)))
    return out


def block_displacements(results, model) -> list:
    """[(magnitude, [ux, uy, uz], point, label), …] — one per rigid BODY.

    Blocks that share an identical transformation moved as one rigid body, so
    they are grouped and reported once: the translation of the group's centroid,
    which is pure translation, free of the apparent movement a body rotation
    injects into an off-centre member.

    Supports are skipped, and so are blocks the solver never moved.
    """
    groups = {}
    for block in model.elements():
        if getattr(block, "is_support", False):
            continue
        T = results.node_attribute(block.graphnode, "transformation")
        if T is None:
            continue
        matrix = T.matrix if hasattr(T, "matrix") else T
        key = tuple(round(value, 9) for row in matrix for value in row)
        groups.setdefault(key, []).append(block)

    out = []
    for members in groups.values():
        T = results.transformation(members[0].graphnode)
        if T is None:
            continue
        centroids = [member.modelgeometry.centroid() for member in members]
        start = [sum(c[i] for c in centroids) / len(centroids) for i in range(3)]

        from compas.geometry import Point

        end = Point(*start).transformed(T)
        translation = [end[i] - start[i] for i in range(3)]

        nodes = [member.graphnode for member in members]
        label = f"block {nodes[0]}" if len(nodes) == 1 else "body " + "-".join(str(n) for n in nodes)
        out.append((_magnitude(translation), translation, list(end), label))
    return out


def support_reactions(results, model) -> list:
    """[(node, [Rx, Ry, Rz], magnitude), …] — total contact force on each support.

    The stored edge resultant is the force on the contact's *v* block, and the
    contact normal points u → v. The Results edge key can be stored reversed, so
    v is identified geometrically: it is the block whose centroid lies on the
    +normal side of the contact point.

    That "u → v" sentence is the part to distrust. Verified against a CRA solve
    of a 15-block arch: the answer this returns is correct — both supports give
    (-/+10.881, 0, +25.852) N, |R| = 28.049 kN, matching the compas_dem viewer to
    the digit, with Rz exactly half the non-support weight — but it is correct
    BECAUSE `contact_normal` hands back the polygon normal, which is flipped
    180° from what CRA stored as the contact frame. Change the normal source and
    every reaction here inverts. See the TRAP note in `contact_normal`.
    """
    blocks = {block.graphnode: block for block in model.elements()}
    centroids = {node: list(block.modelgeometry.centroid()) for node, block in blocks.items()}

    out = []
    for node, block in blocks.items():
        if not getattr(block, "is_support", False):
            continue

        reaction = [0.0, 0.0, 0.0]
        found = False
        for edge in results.edges():
            if node not in edge:
                continue
            other = edge[1] if edge[0] == node else edge[0]
            if other not in centroids:
                continue
            force = results.resultant_global(edge)
            normal = contact_normal(results, edge)
            if not force or normal is None:
                continue

            offset = [centroids[node][i] - centroids[other][i] for i in range(3)]
            side = sum(o * n for o, n in zip(offset, normal))
            sign = 1.0 if side >= 0 else -1.0  # the +normal side is the contact's v
            reaction = [r + sign * f for r, f in zip(reaction, force)]
            found = True

        if found:
            out.append((node, reaction, _magnitude(reaction)))
    return out


def summary(results, model) -> dict:
    """The maximum of every reported quantity, each with a tag saying where.

    Keys: `force`, `stress`, `opening`, `reaction`, `displacement`, each paired
    with `<key>_at` naming the contact ("3-4"), block or support it occurs at —
    `None` when that quantity is absent from this result set.

    Also reports `contacts` (how many carry a force) and `force_total`.
    """

    def top(rows, value_index=0, tag_index=-1):
        """The largest row, or (0.0, None) when there is nothing to report.

        A zero maximum is reported as absent too: "max displacement 0.0 at body
        1-2-3" is worse than saying there was none, which is what an all-zero
        CRA/RBE displacement set means.
        """
        if not rows:
            return 0.0, None
        best = max(rows, key=lambda row: row[value_index])
        value = float(best[value_index])
        if value == 0.0:
            return 0.0, None
        return value, best[tag_index]

    resultants = contact_resultants(results)
    forces = [(magnitude, _edge_label(edge)) for _, _, magnitude, edge in resultants]

    out = {}
    out["contacts"] = len(resultants)
    out["force_total"] = sum(magnitude for magnitude, _ in forces)
    out["force"], out["force_at"] = top(forces)
    out["stress"], out["stress_at"] = top(face_stresses(results))
    out["opening"], out["opening_at"] = top(contact_openings(results))

    reactions = [(magnitude, f"support {node}") for node, _, magnitude in support_reactions(results, model)]
    out["reaction"], out["reaction_at"] = top(reactions)

    displacements = [(magnitude, label) for magnitude, _, _, label in block_displacements(results, model)]
    out["displacement"], out["displacement_at"] = top(displacements)

    return out
