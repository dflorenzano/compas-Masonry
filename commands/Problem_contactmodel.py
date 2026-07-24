#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_contactmodel — set the contact and/or joint model on a Problem.

Single selection: a problem holds ONE contact model and ONE joint model at a
time (setting a new one overwrites the old). Want a different contact model?
Create a different problem.

- ContactModel : MohrCoulomb (phi or mu, cohesion c, tensile cutoff t_c).
- JointModel   : normal / tangential stiffness (kn, kt).

No Rhino geometry — contact properties aren't spatial, so draw_problem() is not
called here.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def set_contact_model(problem):
    friction = rs.GetString(message="Friction input", strings=["phi_degrees", "mu"])
    if not friction:
        return
    kwargs = {}
    if friction == "phi_degrees":
        phi = rs.GetReal("Friction angle phi [deg]", 35.0, 0.0, 90.0)
        if phi is None:
            return
        kwargs["phi"] = phi
    else:
        mu = rs.GetReal("Friction coefficient mu", 0.7, 0.0)
        if mu is None:
            return
        kwargs["mu"] = mu

    c = rs.GetReal("Cohesion c [Pa] (0 = none)", 0.0, 0.0)
    if c is None:
        return
    t_c = rs.GetReal("Tensile cutoff t_c [Pa] (0 = none)", 0.0, 0.0)
    if t_c is None:
        return
    kwargs["c"] = c or None
    kwargs["t_c"] = t_c or None

    problem.add_contact_model("MohrCoulomb", **kwargs)
    print(f"Contact model set: MohrCoulomb {kwargs}")


def set_joint_model(problem):
    kn = rs.GetReal("Normal stiffness kn [N/m]", 1e9, 0.0)
    if kn is None:
        return
    kt = rs.GetReal("Tangential stiffness kt [N/m]", 1e9, 0.0)
    if kt is None:
        return
    problem.add_joint_model(kn, kt)
    print(f"Joint model set: kn={kn}, kt={kt}")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to set the contact model on")
    if name is None:
        return
    problem = session.problems[name]

    option = rs.GetString(message="Problem_contactmodel", strings=["ContactModel", "JointModel"])
    if not option:
        return

    if option == "ContactModel":
        set_contact_model(problem)
    elif option == "JointModel":
        set_joint_model(problem)

    session.save_problems()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
