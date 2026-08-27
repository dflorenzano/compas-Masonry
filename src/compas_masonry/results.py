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
    "face_stresses",
    "contact_openings",
    "tension_contacts",
    "tension_report",
    "block_displacements",
    "support_reactions",
    "summary",
    "CSV_HEADER",
    "block_result_rows",
]

# One row per (block, contact), with the block's displacement repeated on every
# row of that block. Flat and redundant on purpose: it pivots in a spreadsheet
# without anyone having to carry a value down a merged cell.
CSV_HEADER = [
    "block",
    "with",
    "F_magnitude",
    "Fx",
    "Fy",
    "Fz",
    "stress",
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
    for contact in report["contacts"]:
        force = contact["force"]
        rows.append(
            [
                node,
                contact["with"],
                contact["magnitude"],
                force[0],
                force[1],
                force[2],
                cell(contact["stress"]),
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
