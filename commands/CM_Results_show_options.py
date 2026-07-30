#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Results_show_options — draw a stored result set.

- Follows Problem_solve. No result geometry is in the document until this
  command runs.
- Results are stored per solved SET, keyed by solver and boundary conditions
  ("RBE_BC1-BC2"), and drawn under the last BC of that set:
  "Masonry::<i>_<problem>::BC<n>_<bc>::Results::<key>".

Two kinds of result, because the solvers answer different questions:

- **Forces** — contact resultants and contact geometry. This is what CRA and RBE
  produce: `_post_processing_cra` stores an IDENTITY transformation for every
  block and puts the whole answer on the contact edges.
- **Displaced** — a displaced copy of each block from `Results.transformation`,
  exaggerated by `Results.displacement_scale` (fed from
  settings.blockmodel.scale_displacement). This is the LMGC90 shape.

So the mode defaults to Forces when every transformation is an identity: drawing
displaced geometry there would stack an exact duplicate of the model on top of
itself and read as a no-op.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_masonry.boundaryconditions import bc_name
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def stored_results(session, problem_name) -> dict:
    """The results stored for a problem, keyed by result key ("RBE_BC1")."""
    return (session.get("results") or {}).get(problem_name) or {}


def target_bc(problem, results):
    """The (index, bc) a result set is drawn under: the LAST BC it covers.

    Falls back to the first BC if the stored names no longer match the problem's
    boundary conditions (renamed or deleted since the solve).
    """
    names = (results.metadata or {}).get("boundary_conditions") or []
    current = [bc_name(bc, i) for i, bc in enumerate(problem.boundary_conditions)]
    for name in reversed(names):
        if name in current:
            index = current.index(name)
            return index, problem.boundary_conditions[index]
    if not problem.boundary_conditions:
        return None
    return 0, problem.boundary_conditions[0]


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


def show(session, model, problem_name, problem, key, results, mode) -> None:
    picked = target_bc(problem, results)
    if picked is None:
        return warn(f"{key}: the problem has no boundary condition to draw under.")
    index, bc = picked
    name = bc_name(bc, index)
    base = session.bc_layer(problem_name, name, index, "Results")

    drew_anything = False

    if mode in ("Forces", "Both"):
        drawn = session.draw_result_forces(problem_name, bc, index, results, model, key=key)
        if drawn:
            print(f"{key}: drew {drawn} contact resultant(s) under {base}::{key}::Forces")
            report_forces(results)
            drew_anything = True
        else:
            warn(f"{key}: the stored result carries no contact forces.")

    if mode in ("Displaced", "Both"):
        drawn = session.draw_results(problem_name, bc, index, results, model, key=key)
        if drawn:
            print(f"{key}: drew {drawn} displaced block(s) under {base}::{key}::Displaced (scale {session.settings.blockmodel.scale_displacement}).")
            drew_anything = True
        else:
            warn(f"{key}: the stored result has no transformation for any block of the model.")

    if not drew_anything:
        warn(f"{key}: nothing was drawn.")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to show results for", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

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

    # Default to what the first selected result actually holds: CRA/RBE move
    # nothing, so Displaced would draw a duplicate of the model.
    default = "Displaced" if moves_anything(results[selected[0]], model) else "Forces"
    mode = choose("Draw", ["Forces", "Displaced", "Both"], default=default)
    if mode is None:
        return

    fade = choose("Fade the blocks while the results are shown", ["Fade", "Keep"], default="Fade")
    if fade is None:
        return

    for key in selected:
        show(session, model, name, problem, key, results[key], mode)

    transparency = session.settings.blockmodel.results_model_transparency if fade == "Fade" else 0.0
    try:
        session.set_model_transparency(transparency)
        if fade == "Fade":
            print(f"Blocks faded to {transparency:.0%} transparency — visible in Rendered display mode (Shaded ignores render materials).")
    except Exception as e:
        warn(f"The results are drawn, but the blocks could not be faded: {e}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
