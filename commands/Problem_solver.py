#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_solver — select and configure the solver on a Problem (single).

A problem holds ONE solver (problem.solver(...)); selecting a new one replaces
it. Running the solver is a separate step (the Solve command). Each solver has
its own parameter set — only the most relevant knobs are prompted here; the
rest fall back to the compas_dem Solver factory defaults.

Solvers: LMGC90 (contact dynamics), CRA / RBE (rigid-block equilibrium),
PRD / DPRD (piecewise-rigid-displacement convex).
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_dem.problem import Solver
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def config_lmgc90():
    duration = rs.GetReal("Duration [s]", 1.0, 0.0)
    if duration is None:
        return None
    n_steps = rs.GetInteger("Number of steps", 100, 1)
    if n_steps is None:
        return None
    theta = rs.GetReal("Theta (0.5 mid-point, 1.0 backward Euler)", 0.5, 0.0, 1.0)
    if theta is None:
        return None
    return Solver.LMGC90(duration=duration, n_steps=n_steps, theta=theta)


def config_cra():
    d_bnd = rs.GetReal("Penalty boundary d_bnd", 0.001, 0.0)
    if d_bnd is None:
        return None
    eps = rs.GetReal("Convergence tolerance eps", 0.0001, 0.0)
    if eps is None:
        return None
    return Solver.CRA(d_bnd=d_bnd, eps=eps)


def config_prd():
    linear = rs.GetString("Mode", strings=["linear", "nonlinear"]) == "linear"
    mu = rs.GetReal("Friction coefficient mu (0 = use contact model)", 0.0, 0.0)
    if mu is None:
        return None
    return Solver.PRD(linear=linear, mu=mu or None)


def config_dprd():
    linear = rs.GetString("Mode", strings=["linear", "nonlinear"]) == "linear"
    associative = rs.GetString("Friction", strings=["associative", "non_associative"]) == "associative"
    mu = rs.GetReal("Friction coefficient mu (0 = use contact model)", 0.0, 0.0)
    if mu is None:
        return None
    return Solver.DPRD(linear=linear, associative=associative, mu=mu or None)


def config_rbe():
    return Solver.RBE()


CONFIGURATORS = {
    "LMGC90": config_lmgc90,
    "CRA": config_cra,
    "PRD": config_prd,
    "DPRD": config_dprd,
    "RBE": config_rbe,
}


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to set the solver on")
    if name is None:
        return
    problem = session.problems[name]

    kind = rs.GetString(message="Solver", strings=list(CONFIGURATORS.keys()))
    if not kind:
        return

    solver = CONFIGURATORS[kind]()
    if solver is None:
        return

    problem.solver(solver)
    session.save_problems()
    print(f"Solver set on {name}: {solver}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
