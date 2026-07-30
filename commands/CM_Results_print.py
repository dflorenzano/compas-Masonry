#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Results_print — print a stored result set in the command window.

Reading the numbers without drawing anything, which is what you want when
comparing runs or checking an order of magnitude.

Scopes:

- **Summary** — the maximum of every quantity, each tagged with the contact,
  block or support it occurs at, plus the contact count and total force.
- **Contacts** — one row per contact: resultant, magnitude, stress, opening.
- **Blocks** — one row per moved rigid body: displacement vector and magnitude.
  CRA and RBE move nothing, so this is empty for their results by design.
- **Reactions** — the total contact force on each support, and their sum.

Every quantity is derived by `compas_masonry.results`, the same module the force
drawing uses, so a printed number and a drawn arrow cannot disagree.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_masonry.inputs import choose
from compas_masonry.results import block_displacements
from compas_masonry.results import contact_openings
from compas_masonry.results import contact_resultants
from compas_masonry.results import face_stresses
from compas_masonry.results import summary
from compas_masonry.results import support_reactions
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


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


def print_summary(key, results, model) -> None:
    values = summary(results, model)
    meta = results.metadata or {}

    print(f"\n=== {key} ===")
    solver = meta.get("solver")
    if solver:
        bcs = ", ".join(meta.get("boundary_conditions") or [])
        print(f"solver     : {solver}   boundary conditions: {bcs}")
    if meta.get("solved_at"):
        print(f"solved     : {meta['solved_at']}  ({meta.get('duration_s', '?')} s)")
    if meta.get("mu") is not None:
        print(f"friction mu: {meta['mu']:.4f}")

    print(f"contacts   : {values['contacts']} carrying force, total |F| = {values['force_total']:.6g}")

    rows = [
        ("max |F|", values["force"], values["force_at"]),
        ("max stress", values["stress"], values["stress_at"]),
        ("max opening", values["opening"], values["opening_at"]),
        ("max reaction", values["reaction"], values["reaction_at"]),
        ("max displacement", values["displacement"], values["displacement_at"]),
    ]
    for label, value, at in rows:
        print(f"{label:<18}: -" if at is None else f"{label:<18}: {value:.6g}   at {at}")


def print_contacts(results) -> None:
    resultants = contact_resultants(results)
    if not resultants:
        return warn("This result set carries no contact forces.")

    stresses = {label: value for value, _, label in face_stresses(results)}
    openings = {label: value for value, _, label in contact_openings(results)}

    header = f"{'contact':<12}{'|F|':>14}{'Fx':>14}{'Fy':>14}{'Fz':>14}{'stress':>14}{'opening':>14}"
    print("\n" + header)
    print("-" * len(header))
    for _, vector, magnitude, edge in sorted(resultants, key=lambda row: -row[2]):
        label = f"{edge[0]}-{edge[1]}"
        stress = stresses.get(label)
        opening = openings.get(label)
        print(
            f"{label:<12}{magnitude:>14.6g}{vector[0]:>14.6g}{vector[1]:>14.6g}{vector[2]:>14.6g}"
            f"{('-' if stress is None else format(stress, '.6g')):>14}"
            f"{('-' if opening is None else format(opening, '.6g')):>14}"
        )
    print(f"{len(resultants)} contact(s).")


def print_blocks(results, model) -> None:
    moved = [row for row in block_displacements(results, model) if row[0] > 0]
    if not moved:
        return warn("No block moved in this result set — CRA and RBE return contact forces, not displacements.")

    header = f"{'body':<20}{'|u|':>14}{'ux':>14}{'uy':>14}{'uz':>14}"
    print("\n" + header)
    print("-" * len(header))
    for magnitude, translation, _, label in sorted(moved, key=lambda row: -row[0]):
        print(f"{label:<20}{magnitude:>14.6g}{translation[0]:>14.6g}{translation[1]:>14.6g}{translation[2]:>14.6g}")
    print(f"{len(moved)} moved bod(y/ies).")


def print_reactions(results, model) -> None:
    rows = support_reactions(results, model)
    if not rows:
        return warn("No support reaction could be resolved — the model has no supports, or no contact reaches them.")

    header = f"{'support':<12}{'|R|':>14}{'Rx':>14}{'Ry':>14}{'Rz':>14}"
    print("\n" + header)
    print("-" * len(header))
    total = [0.0, 0.0, 0.0]
    for node, reaction, magnitude in sorted(rows, key=lambda row: -row[2]):
        print(f"{node:<12}{magnitude:>14.6g}{reaction[0]:>14.6g}{reaction[1]:>14.6g}{reaction[2]:>14.6g}")
        total = [t + r for t, r in zip(total, reaction)]
    print(f"{'sum':<12}{'':>14}{total[0]:>14.6g}{total[1]:>14.6g}{total[2]:>14.6g}")
    print("The sum should balance the applied loads; a large residual means the solve did not converge.")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to print results for", keywords=True)
    if name is None:
        return

    picked = choose_result(session, name)
    if picked is None:
        return
    key, results = picked

    scope = choose("Print", ["Summary", "Contacts", "Blocks", "Reactions", "All"], default="Summary")
    if scope is None:
        return

    if scope in ("Summary", "All"):
        print_summary(key, results, model)
    if scope in ("Contacts", "All"):
        print_contacts(results)
    if scope in ("Blocks", "All"):
        print_blocks(results, model)
    if scope in ("Reactions", "All"):
        print_reactions(results, model)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
