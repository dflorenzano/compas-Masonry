#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_solve_options — solve a Problem for a selection of its boundary conditions.

- Pick the problem, then the boundary conditions to include. Every selected BC
  is solved TOGETHER, in the order the BC list gives — there is no stepped
  solve, and no separate solve order to configure.
- Solving draws NOTHING. One `Results` per solve is stored on the session under
  a key naming the solver and the BCs ("RBE_BC1-BC2"); Results_show is what puts
  geometry in the document.
- A key that is already stored is reused rather than re-solved, unless a
  re-solve is asked for explicitly.

Three things about the environment shape this command, all verified rather than
assumed:

1. `ipopt` — compas_cra hands its pyomo model to `SolverFactory("ipopt")`, an
   executable lookup on PATH. Rhino does not inherit a shell PATH, so
   `session.ensure_solver_path()` runs first and reports what it found.
2. `BlockModel.solve(problem, boundary_conditions=[...])` assigns
   `problem.boundary_conditions`, which has no setter -> `AttributeError` before
   any solver runs. Until that upstream fix lands, the BC list is swapped on the
   private attribute around the call and restored in a `finally` — which is also
   non-destructive, where a plain setter would drop the problem's other BCs.
3. CRA/RBE dereference `block.material.density`, and LMGC90 refuses more than
   one BC. Both are checked up front, so a failure names the command to run
   instead of surfacing a traceback.

`Results` is a compas Data, so it serializes onto the session as is.
"""

import pathlib
import time

from compas_dem.models import BlockModel
from compas_masonry.boundaryconditions import bc_name
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def result_key(solver_name, names) -> str:
    """Key a result set by its solver and the BCs it covers: "RBE_BC1-BC2"."""
    return f"{solver_name}_{'-'.join(names)}"


def store(session, problem_name, key, results) -> None:
    """Persist one Results on the session, keyed by problem and result key."""
    stored = session.setdefault("results", dict)
    problem_results = stored.setdefault(problem_name, {})
    problem_results[key] = results
    session["results"] = stored


def check_ready(model, problem, name):
    """Return the first unmet precondition for solving, or None if ready."""
    if model.graph.number_of_edges() == 0:
        return "No contacts in the model. Run Model_contacts first — every solver works off the contact interfaces."

    if getattr(problem, "_solver", None) is None:
        return f"{name} has no solver. Run Problem_solver first."

    if not problem.contact_properties.contact_model:
        return f"{name} has no contact law. Run Problem_contactlaw first — check_model_validity requires one."

    has_supports = bool(problem.supports) or any(block.is_support for block in model.elements())
    if not has_supports:
        return "The model has no supports. Run Model_supports first."

    if not problem.boundary_conditions:
        return f"{name} has no boundary condition. Run Problem_createbc first."

    # CRA/RBE read block.material.density directly. compas_dem raises a clear
    # ValueError now, but naming the command to run is more useful than that.
    missing = [b.graphnode for b in model.elements() if b.material is None or b.material.density is None]
    if missing:
        shown = ", ".join(str(n) for n in missing[:5])
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return f"Blocks {shown}{more} have no material with a density. Run Model_material, then Model_materialassign."

    return None


def solve(model, problem, bcs):
    """Solve `problem` for exactly `bcs`, without mutating the problem.

    `boundary_conditions` is deliberately NOT passed: `BlockModel.solve` would
    then do `problem.boundary_conditions = boundary_conditions`, and that
    property has no setter — verified, it raises `AttributeError: can't set
    attribute` before any solver runs. Left empty, solve reads
    `problem.boundary_conditions` instead, so swapping the private list here
    selects the subset and the `finally` puts the full list back.

    Returns the Results, or None on failure (reported through `warn`).
    """
    original = problem._boundary_conditions
    try:
        problem._boundary_conditions = list(bcs)
        return model.solve(problem)
    except ImportError as e:
        # the solver backends (compas_cra, compas_lmgc90, ...) are optional
        warn(f"The solver backend is not installed: {e}")
    except NotImplementedError as e:
        warn(f"The solver does not support this selection: {e}")
    except Exception as e:
        warn(f"Solve failed: {e}")
    finally:
        problem._boundary_conditions = original
    return None


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to solve", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    not_ready = check_ready(model, problem, name)
    if not_ready:
        return warn(not_ready)

    solver = problem._solver

    picked = session.choose_bcs(problem, message="Boundary conditions to solve (all are solved together)")
    if not picked:
        return

    if solver.name == "LMGC90" and len(picked) > 1:
        return warn("The LMGC90 backend takes only one boundary condition per problem. Select a single BC, or use CRA / RBE.")

    names = [bc_name(bc, i) for i, bc in picked]
    key = result_key(solver.name, names)

    stored = (session.get("results") or {}).get(name) or {}
    if key in stored:
        again = choose(f"{key} has already been solved", ["Reuse", "Solve"], default="Reuse")
        if again is None:
            return
        if again == "Reuse":
            print(f"Reusing the stored result for {key}. Next: Results_show.")
            return

    # ipopt is an executable, looked up on PATH by compas_cra's pyomo model
    ipopt = session.ensure_solver_path()
    if ipopt:
        print(f"ipopt: {ipopt}")
    elif solver.name in ("CRA", "RBE"):
        warn(f"ipopt was not found on PATH, nor in settings.solver_bin ({session.settings.solver_bin}).")
        print("CRA and RBE solve through it, so this will fail. Set the directory in Session_settings > Solver Executables Directory.")

    print(f"Solving {name} ({solver.name}) for {len(picked)} boundary condition(s): {', '.join(names)}")

    started = time.time()
    results = solve(model, problem, [bc for _, bc in picked])
    if results is None:
        return
    elapsed = time.time() - started

    results.metadata["solver"] = solver.name
    results.metadata["boundary_conditions"] = names
    results.metadata["solved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results.metadata["duration_s"] = round(elapsed, 3)

    try:
        store(session, name, key, results)
    except Exception as e:
        return warn(f"Solved, but the result could not be stored on the session: {e}")

    print(f"Solved in {elapsed:.1f}s, stored on {name} as {key}.")
    print("Next: Results_show to draw it (nothing is drawn by solving).")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
