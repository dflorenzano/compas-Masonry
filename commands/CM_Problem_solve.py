#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_solve — solve a Problem.

**Every boundary condition group on the problem is solved.** There is no
selection: `problem.solve()` takes no arguments and applies every group it
carries. A different set of loads means a different problem — duplicate it in
Problem_create. `Problem.set_solve_order()` exists upstream if the order matters;
no command exposes it yet.

Solving draws NOTHING. One `Results` per solve is stored on the session under a
key naming the solver and the time it ran ("RBE_2026-08-04T15-30-12"), so a
re-solve after changing a material or a contact law never overwrites the earlier
run and the two can be compared. Results_show is what puts geometry in the
document.

Three things about the environment shape this command, all verified rather than
assumed:

1. `ipopt` — compas_cra hands its pyomo model to `SolverFactory("ipopt")`, an
   executable lookup on PATH. Rhino does not inherit a shell PATH, so
   `session.ensure_solver_path()` runs first and reports what it found.
2. **CRA and RBE ignore boundary conditions entirely.** `cra_solve` and
   `rbe_solve` take the problem, the model, a friction coefficient and a density
   — and never read `problem.boundary_conditions`. They solve self-weight
   equilibrium. So a problem carrying loads or prescribed movements does not
   fail under CRA: it returns a **self-weight answer that looks like a result**,
   which is worse. Refused here, because nothing downstream will.
3. CRA/RBE dereference `block.material.density`, and need a contact law for the
   friction coefficient. Both are checked so a failure names the fix.

`Results` is a compas Data, so it serializes onto the session as is.
"""

import pathlib
import time

from compas_dem.models import BlockModel
from compas_masonry.boundaryconditions import conditions_of
from compas_masonry.boundaryconditions import loads_of
from compas_masonry.results import tension_report
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


# `cra_accepts_loads()` lived here and was deleted on 2026-08-07. It inspected
# `compas_cra.equilibrium.cra_solve` for a `loads=` parameter, because compas_dem
# used to pass one and the released compas_cra would raise a TypeError mid-solve.
# compas_dem no longer passes loads to CRA at all — `cra_solve` takes the problem,
# the model, mu and density and reads no boundary conditions — so there is nothing
# to be compatible with. What replaced it is the guard below, which refuses the
# solve outright rather than checking whether it would crash.


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

    if Session.solver_of(problem) is None:
        return f"{name} has no solver. Run Problem_setsolver first."

    if not problem.contact_properties.contact_model:
        return f"{name} has no contact law. Run Problem_contactlaw first — check_model_validity requires one."

    # supports live on the model only — a problem never carries a copy
    if not any(block.is_support for block in model.elements()):
        return "The model has no supports. Run Model_supports first."

    solver_name = Session.solver_of(problem).name

    # CRA/RBE read no boundary conditions at all — they solve self-weight
    # equilibrium — so a problem carrying any would come back with a plausible
    # answer to a question nobody asked. Refuse instead of returning that.
    if solver_name in ("CRA", "RBE"):
        groups = problem.boundary_conditions
        conditions = sum(len(conditions_of(group)) for group in groups)
        if conditions:
            listed = ", ".join(group.name for group in groups)
            return (
                f"{name} carries {conditions} boundary condition(s) in [{listed}], and {solver_name} applies none of them — "
                f"it solves self-weight equilibrium only, so it would return a result that silently ignores them. "
                "Use LMGC90, or remove them in Problem_loads / Problem_displacements."
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

    model: BlockModel = session.model
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

    solver = Session.solver_of(problem)
    key = result_key(solver.name)

    # ipopt is an executable, looked up on PATH by compas_cra's pyomo model
    ipopt = session.ensure_solver_path()
    if ipopt:
        print(f"ipopt: {ipopt}")
    elif solver.name in ("CRA", "RBE"):
        warn(f"ipopt was not found on PATH, nor in settings.solver_bin ({session.settings.solver_bin}).")
        print("CRA and RBE solve through it, so this will fail. Set the directory in Session_settings > Solver Executables Directory.")

    groups = problem.boundary_conditions
    if groups:
        loads = sum(len(loads_of(group)) for group in groups)
        movements = sum(len(group.displacements) for group in groups)
        listed = ", ".join(group.name for group in groups)
        print(f"Solving {name} ({solver.name}) with {loads} load(s) and {movements} prescribed movement(s) in [{listed}].")
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

    # A solve that succeeds is not the same as a solve that is admissible: masonry
    # takes no tension, so a converged answer holding tensile contact corners is
    # still not one the structure can deliver. Said at the moment it is produced,
    # because nothing else here would report it and Results_show may never be run.
    reported = tension_report(results)
    if reported is not None:
        expected, message = reported
        if expected:
            print(message)
        else:
            warn(message)

    print("Next: Results_show to draw it (nothing is drawn by solving).")
    session.record(f"Solve {name}: {key}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
