#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Results_show_options — draw a stored result set.

- Follows Problem_solve. No result geometry is in the document until this
  command runs.
- Results are stored per solve, keyed by solver and timestamp
  ("RBE_2026-08-04T15-30-12"), and drawn at PROBLEM level:
  "Masonry::<i>_<problem>::Results::<key>".

  A problem IS the load case, so a result belongs to the problem. The timestamp
  means a re-solve after changing a material or a contact law is kept beside the
  earlier run instead of overwriting it.

Two kinds of result, because the solvers answer different questions:

- **Forces** — contact resultants and contact geometry. This is what CRA and RBE
  produce: `_post_processing_cra` stores an IDENTITY transformation for every
  block and puts the whole answer on the contact edges.
- **Displaced** — a displaced copy of each block from `Results.transformation`,
  exaggerated by `Results.displacement_scale` (fed from
  settings.blockmodel.scale_displacement). This is the LMGC90 shape.

So Displaced is only offered for a solver that produces displacements, read off
the result key rather than off the problem's current solver — the setting may
have changed since the solve, the key cannot. `moves_anything` stays as the
fallback for a result whose key does not name a known solver.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn

# Solvers that move blocks. CRA and RBE answer on the contact edges and store an
# identity transformation per block, so a Displaced view of one of their results
# stacks an exact copy of the model on itself and reads as a no-op.
DISPLACEMENT_SOLVERS = ("LMGC90", "3DEC")


def stored_results(session, problem_name) -> dict:
    """The results stored for a problem, keyed by result key ("RBE_2026-08-04T15-30-12")."""
    return (session.get("results") or {}).get(problem_name) or {}


def solver_of(key) -> str:
    """The solver named by a result key: "RBE_2026-08-04T15-30-12" -> "RBE"."""
    return key.split("_")[0] if key else ""


def offers_displacement(keys, results, model) -> bool:
    """Whether Displaced is worth offering for the selected result sets.

    Decided by the solver named in the key, not by the problem's current solver:
    Problem_setsolver may have been run since, and re-pointing it at LMGC90 does not
    retroactively give an RBE result any displacements.
    """
    for key in keys:
        if solver_of(key) in DISPLACEMENT_SOLVERS:
            return True
    # a key that names no known solver (hand-built, or a solver added later):
    # fall back to asking the result itself
    unknown = [k for k in keys if solver_of(k) not in DISPLACEMENT_SOLVERS + ("CRA", "RBE")]
    return any(moves_anything(results[k], model) for k in unknown)


def moves_anything(results, model) -> bool:
    """True if any block carries a non-identity transformation.

    CRA/RBE store an identity per block, so this separates a force result from a
    displacement result without asking which solver ran. Read through
    `node_attribute` rather than `transformation()`, to skip the
    displacement_scale amplification.
    """
    for block in model.elements():
        T = results.node_attribute(block.graphnode, "transformation")
        if T is None:
            continue
        matrix = T.matrix if hasattr(T, "matrix") else T
        for i, row in enumerate(matrix):
            for j, value in enumerate(row):
                expected = 1.0 if i == j else 0.0
                if abs(value - expected) > 1e-12:
                    return True
    return False


def report_forces(results) -> None:
    """Print the force magnitudes, so there is a number to sanity-check."""
    magnitudes = [m for m in (results.force_magnitude(edge) for edge in results.edges()) if m]
    if not magnitudes:
        return
    print(f"  {len(magnitudes)} contact resultant(s): max {max(magnitudes):.4g}, total {sum(magnitudes):.4g}")


def show(session, model, problem_name, key, results, mode) -> None:
    base = session.results_layer(problem_name, key)

    drew_anything = False

    if mode in ("Forces", "Both"):
        drawn = session.draw_result_forces(problem_name, results, model, key=key)
        if drawn:
            print(f"{key}: drew {drawn} contact resultant(s) under {base}::Forces")
            report_forces(results)
            drew_anything = True
        else:
            warn(f"{key}: the stored result carries no contact forces.")

    if mode in ("Displaced", "Both"):
        drawn = session.draw_results(problem_name, results, model, key=key)
        if drawn:
            print(f"{key}: drew {drawn} displaced block(s) under {base}::Displaced (scale {session.settings.blockmodel.scale_displacement}).")
            drew_anything = True
        else:
            warn(f"{key}: the stored result has no transformation for any block of the model.")

    if not drew_anything:
        warn(f"{key}: nothing was drawn.")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.model
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to show results for", keywords=True)
    if name is None:
        return

    results = stored_results(session, name)
    if not results:
        return warn(f"No results stored for {name}. Run Problem_solve first.")

    keys = sorted(results)
    if len(keys) == 1:
        selected = keys
    else:
        picked = rs.MultiListBox(keys, message="Result set(s) to draw", title="Results")
        if not picked:
            return
        selected = list(picked)

    # Only offer Displaced for a solver that produces displacements. For a
    # CRA/RBE set there is nothing to choose, so do not ask at all.
    if offers_displacement(selected, results, model):
        mode = choose("Draw", ["Forces", "Displaced", "Both"], default="Displaced")
        if mode is None:
            return
    else:
        mode = "Forces"
        print(f"{solver_of(selected[0])} reports contact forces, not displacements — drawing forces.")

    fade = choose("Fade the blocks while the results are shown", ["Fade", "Keep"], default="Fade")
    if fade is None:
        return

    # after the last bail-out, before the first change — see Session_undo
    session.ensure_baseline()

    for key in selected:
        show(session, model, name, key, results[key], mode)

    # Record WHAT is on screen. Solving draws nothing and this command's choices
    # (which keys, and Forces/Displaced/Both) exist nowhere else — so without this
    # an undo, which clears the whole layer tree before redrawing, silently threw
    # the result view away with no means of rebuilding it. Kept per problem, so
    # showing results for a second problem does not forget the first.
    shown = session.get("shown_results") or {}
    shown[name] = {"keys": list(selected), "mode": mode}
    session["shown_results"] = shown

    amount = session.settings.blockmodel.results_model_transparency if fade == "Fade" else 0.0
    try:
        touched = session.fade_model(amount)
        if fade == "Fade":
            print(f"{touched} block object(s) faded {amount:.0%} toward white — a custom object colour, so it shows in every display mode.")
        else:
            print(f"{touched} block object(s) restored to their layer colour.")
    except Exception as e:
        warn(f"The results are drawn, but the blocks could not be faded: {e}")

    # Showing results IS a state change, because `shown_results` above is the only
    # record of what is on screen. Without recording here it never reaches a
    # snapshot, and the first undo deletes it along with the rest of the working
    # copy — which is exactly how the result view went missing the first time.
    session.record(f"Show results: {name} ({mode})")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
