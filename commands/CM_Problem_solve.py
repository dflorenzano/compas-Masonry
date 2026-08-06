#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_solve — solve a Problem.

**Every boundary condition on the problem is solved.** There is no selection: a
problem IS the load case, and a different set of loads means a different problem
(duplicate it in Problem_create). The BC multi-select this command used to open
is gone with the compas_dem restructure, along with the private-list swap that
worked around `boundary_conditions` having no setter — `problem.solve()` takes no
arguments at all now.

Solving draws NOTHING. One `Results` per solve is stored on the session under a
key naming the solver and the time it ran ("RBE_2026-08-04T15-30-12"), so a
re-solve after changing a material or a contact law never overwrites the earlier
run and the two can be compared. Results_show is what puts geometry in the
document.

Four things about the environment shape this command, all verified rather than
assumed:

1. `ipopt` — compas_cra hands its pyomo model to `SolverFactory("ipopt")`, an
   executable lookup on PATH. Rhino does not inherit a shell PATH, so
   `session.ensure_solver_path()` runs first and reports what it found.
2. **compas_cra must be new enough to take external loads.** compas_dem now
   passes `loads=` into `cra_solve`/`rbe_solve`; a site-env carrying the released
   compas_cra raises `TypeError: cra_solve() got an unexpected keyword argument
   'loads'` in the middle of a solve. Checked up front instead — see
   `cra_accepts_loads`.
3. **CRA and RBE cannot apply prescribed movements.** They have no displacement
   degrees of freedom for support blocks, so compas_dem refuses rather than
   returning a self-weight answer for a settlement problem. Checked here so the
   message names the command to run.
4. CRA/RBE dereference `block.material.density`, and need a contact law for the
   friction coefficient. Both are checked so a failure names the fix.

`Results` is a compas Data, so it serializes onto the session as is.
"""

import pathlib
import time

from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def result_key(solver_name) -> str:
    """Key a result set by its solver and when it ran: "RBE_2026-08-04T15-30-12".

    A problem is the load case, so there are no BC names left to key by. The
    timestamp means a re-solve after changing a material or a contact law is kept
    beside the earlier run rather than overwriting it — colons are avoided because
    the key becomes a Rhino layer name.
    """
    return f"{solver_name}_{time.strftime('%Y-%m-%dT%H-%M-%S')}"


def cra_accepts_loads() -> bool:
    """Whether the installed compas_cra takes the `loads=` compas_dem passes it.

    compas_dem applies external loads in CRA/RBE by handing `loads=` to
    `cra_solve`. Released compas_cra has no such parameter, so the solve dies
    mid-run with a TypeError that says nothing about which package is stale. The
    fix is the unreleased `feature/external-loads` fork.
    """
    try:
        import inspect

        from compas_cra.equilibrium import cra_solve
    except ImportError:
        return True  # not installed at all: a different error, reported elsewhere
    try:
        return "loads" in inspect.signature(cra_solve).parameters
    except (TypeError, ValueError):
        return True


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

    if problem.solver is None:
        return f"{name} has no solver. Run Problem_setsolver first."

    if not problem.contact_properties.contact_model:
        return f"{name} has no contact law. Run Problem_contactlaw first — check_model_validity requires one."

    # supports live on the model only — a problem never carries a copy
    if not any(block.is_support for block in model.elements()):
        return "The model has no supports. Run Model_supports first."

    solver_name = problem.solver.name

    # CRA/RBE have no displacement DOFs for support blocks, so compas_dem refuses
    # a problem carrying one rather than silently returning a self-weight answer
    if solver_name in ("CRA", "RBE") and problem.displacements:
        return (
            f"{name} carries {len(problem.displacements)} prescribed movement(s), which {solver_name} cannot apply "
            "(support blocks have no displacement degrees of freedom). Use LMGC90, PRD or BLA, or remove them in Problem_displacements."
        )

    if solver_name in ("CRA", "RBE") and not cra_accepts_loads():
        return (
            "The installed compas_cra does not accept external loads, so this solve would fail inside the backend "
            "(TypeError: cra_solve() got an unexpected keyword argument 'loads'). "
            "Install the compas_cra 'feature/external-loads' branch into the Rhino site-env."
        )

    # CRA/RBE read block.material.density directly. compas_dem raises a clear
    # ValueError now, but naming the command to run is more useful than that.
    missing = [b.graphnode for b in model.elements() if b.material is None or b.material.density is None]
    if missing:
        shown = ", ".join(str(n) for n in missing[:5])
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return f"Blocks {shown}{more} have no material with a density. Run Model_material, then Model_materialassign."

    return None


def solve(problem):
    """Run the problem's solver over every boundary condition it carries.

    `problem.solve()` takes no arguments: solving moved onto Problem, and the
    subset selection is gone. The private-list swap that used to live here worked
    around `BlockModel.solve` assigning to a property with no setter — both the
    assignment and the property are gone.

    Returns the Results, or None on failure (reported through `warn`).
    """
    try:
        return problem.solve()
    except ImportError as e:
        # the solver backends (compas_cra, compas_lmgc90, ...) are optional
        warn(f"The solver backend is not installed: {e}")
    except NotImplementedError as e:
        warn(f"The solver does not support this problem: {e}")
    except Exception as e:
        warn(f"Solve failed: {e}")
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

    solver = problem.solver
    key = result_key(solver.name)

    # ipopt is an executable, looked up on PATH by compas_cra's pyomo model
    ipopt = session.ensure_solver_path()
    if ipopt:
        print(f"ipopt: {ipopt}")
    elif solver.name in ("CRA", "RBE"):
        warn(f"ipopt was not found on PATH, nor in settings.solver_bin ({session.settings.solver_bin}).")
        print("CRA and RBE solve through it, so this will fail. Set the directory in Session_settings > Solver Executables Directory.")

    conditions = problem.boundary_conditions
    if conditions:
        print(f"Solving {name} ({solver.name}) with {len(problem.loads)} load(s) and {len(problem.displacements)} prescribed movement(s).")
    else:
        print(f"Solving {name} ({solver.name}) under self-weight only.")

    # Right before the solve: everything above either bails out or only reads, and
    # a solve is the one action here that is expensive to repeat — so the state it
    # was launched from is worth being able to return to.
    session.ensure_baseline()

    started = time.time()
    results = solve(problem)
    if results is None:
        return
    elapsed = time.time() - started

    results.metadata["solver"] = solver.name
    results.metadata["solved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results.metadata["duration_s"] = round(elapsed, 3)

    try:
        store(session, name, key, results)
    except Exception as e:
        return warn(f"Solved, but the result could not be stored on the session: {e}")

    print(f"Solved in {elapsed:.1f}s, stored on {name} as {key}.")
    print("Next: Results_show to draw it (nothing is drawn by solving).")
    session.record(f"Solve {name}: {key}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
