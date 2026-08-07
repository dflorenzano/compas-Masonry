#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Results_block — the result data of the blocks you select.

Results_print reports the whole set; this answers "what happened to *this*
block": its displacement, and every contact it takes part in, with the force,
stress and opening at each — including which neighbour is on the other side.

Selection is by picking blocks in the viewport, resolved to graph nodes through
the persistent `element_guid` User Text tag (never by object name, which a
redraw does not preserve).

Two outputs, chosen at the end:

- **Print** — a table per selected block in the command window.
- **Tag** — the same numbers written onto the block's Rhino object as User Text,
  so they show in the properties panel and survive being saved with the file.
  Cleared and rewritten on each run, and removed if you pick a different result.
"""

import pathlib

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.inputs import choose
from compas_masonry.results import block_displacements
from compas_masonry.results import contact_openings
from compas_masonry.results import contact_resultants
from compas_masonry.results import face_stresses
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn

import rhinoscriptsyntax as rs  # type: ignore

# User Text keys this command owns, so a re-run can clear its own tags without
# touching element_guid / material_name / is_support.
TAG_KEYS = ["result_key", "result_displacement", "result_contacts", "result_force_total"]


def choose_result(session, problem_name):
    """Pick one stored result set. Returns (key, results) or None."""
    stored = (session.get("results") or {}).get(problem_name) or {}
    if not stored:
        warn(f"No results stored for {problem_name}. Run Problem_solve first.")
        return None

    keys = sorted(stored)
    if len(keys) == 1:
        return keys[0], stored[keys[0]]

    key = rs.ListBox(keys, message="Result set", title="Results")
    if not key:
        return None
    return key, stored[key]


def selected_blocks(session, model):
    """Select Rhino objects and resolve them to (node, guid) pairs."""
    guids = compas_rhino.objects.select_objects(message="Select the blocks to report on")
    if not guids:
        return []

    guid_element_map = session.guid_element_map(model)
    out = []
    for guid in guids:
        node = session.find_node(guid, guid_element_map)
        if node is not None:
            out.append((node, guid))
    return sorted(set(out))


def block_report(node, results, model, displacements, stresses, openings, resultants):
    """Everything known about one block in this result set."""
    contacts = []
    for _, vector, magnitude, edge in resultants:
        if node not in edge:
            continue
        other = edge[1] if edge[0] == node else edge[0]
        label = f"{edge[0]}-{edge[1]}"
        contacts.append(
            {
                "with": other,
                "label": label,
                "force": vector,
                "magnitude": magnitude,
                "stress": stresses.get(label),
                "opening": openings.get(label),
            }
        )
    contacts.sort(key=lambda c: -c["magnitude"])

    return {
        "node": node,
        "displacement": displacements.get(node),
        "contacts": contacts,
        "force_total": sum(c["magnitude"] for c in contacts),
    }


def print_report(report) -> None:
    node = report["node"]
    print(f"\n--- block {node} ---")

    displacement = report["displacement"]
    if displacement is None:
        print("displacement : - (this solver returned no displacements)")
    else:
        magnitude, translation, label = displacement
        print(f"displacement : |u| = {magnitude:.6g}   [{translation[0]:.6g}, {translation[1]:.6g}, {translation[2]:.6g}]   ({label})")

    if not report["contacts"]:
        print("contacts     : none carrying force")
        return

    print(f"contacts     : {len(report['contacts'])}, total |F| = {report['force_total']:.6g}")
    header = f"  {'with':<8}{'|F|':>14}{'Fx':>14}{'Fy':>14}{'Fz':>14}{'stress':>14}{'opening':>14}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for contact in report["contacts"]:
        force = contact["force"]
        stress = contact["stress"]
        opening = contact["opening"]
        print(
            f"  {contact['with']:<8}{contact['magnitude']:>14.6g}{force[0]:>14.6g}{force[1]:>14.6g}{force[2]:>14.6g}"
            f"{('-' if stress is None else format(stress, '.6g')):>14}"
            f"{('-' if opening is None else format(opening, '.6g')):>14}"
        )


def tag_block(session, guid, key, report) -> None:
    """Write the block's result data onto its Rhino object as User Text."""
    displacement = report["displacement"]
    session.set_user_params(
        guid,
        {
            "result_key": key,
            "result_displacement": None if displacement is None else displacement[1],
            "result_contacts": [
                {"with": c["with"], "force_magnitude": c["magnitude"], "stress": c["stress"], "opening": c["opening"]} for c in report["contacts"]
            ],
            "result_force_total": report["force_total"],
        },
    )


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.model
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to report on", keywords=True)
    if name is None:
        return

    picked = choose_result(session, name)
    if picked is None:
        return
    key, results = picked

    blocks = selected_blocks(session, model)
    if not blocks:
        return warn("No block resolved from the selection. Select the block meshes under Masonry::Model.")

    # derived once for the whole set, then filtered per block
    resultants = contact_resultants(results)
    stresses = {label: value for value, _, label in face_stresses(results)}
    openings = {label: value for value, _, label in contact_openings(results)}

    displacements = {}
    for magnitude, translation, _, label in block_displacements(results, model):
        # a body groups several blocks under one transformation
        for token in label.replace("block ", "").replace("body ", "").split("-"):
            if token.isdigit():
                displacements[int(token)] = (magnitude, translation, label)

    output = choose("Output", ["Print", "Tag", "Both"], default="Print")
    if output is None:
        return

    print(f"\n=== {key}: {len(blocks)} block(s) ===")
    for node, guid in blocks:
        report = block_report(node, results, model, displacements, stresses, openings, resultants)
        if output in ("Print", "Both"):
            print_report(report)
        if output in ("Tag", "Both"):
            tag_block(session, guid, key, report)

    if output in ("Tag", "Both"):
        print(f"\nTagged {len(blocks)} block(s) with their {key} data (visible in the properties panel).")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
