#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Problem_contactlaw_options — set the contact law and/or joint model on a Problem.

Renamed from Problem_contactmodel per the dev notes ("contact law" is the term
used in the Problem API: one problem = one solver, one contact law).

- No string prompt: ContactLaw / JointModel are command line options, and every
  parameter is shown at once. The friction parameter collapses to phi or mu
  depending on the FrictionInput toggle.
- Single selection: a problem holds ONE contact law and ONE joint model at a
  time (setting a new one overwrites the old). Want a different contact law?
  Duplicate the problem.
- No Rhino geometry: contact properties aren't spatial.
"""

import pathlib

from compas_dem.models import BlockModel
from compas_masonry.inputs import Options
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def set_contact_law(problem):
    options = Options("Contact law (MohrCoulomb)")
    options.add_toggle("friction", False, off="Phi", on="Mu", text=True, keyword="FrictionInput")
    options.add_number("phi", 35.0, minimum=0.0, maximum=90.0, keyword="Phi", units="deg", prompt="Friction angle phi", visible=lambda v: v["friction"] == "Phi")
    options.add_number("mu", 0.7, minimum=0.0, keyword="Mu", prompt="Friction coefficient mu", visible=lambda v: v["friction"] == "Mu")
    options.add_number("c", 0.0, minimum=0.0, keyword="Cohesion", units="Pa", prompt="Cohesion c (0 = none)")
    options.add_number("t_c", 0.0, minimum=0.0, keyword="TensileCutoff", units="Pa", prompt="Tensile cutoff t_c (0 = none)")

    values = options.get()
    if values is None:
        return

    kwargs = {"c": values["c"] or None, "t_c": values["t_c"] or None}
    if values["friction"] == "Mu":
        kwargs["mu"] = values["mu"]
    else:
        kwargs["phi"] = values["phi"]

    problem.set_contact_model("MohrCoulomb", **kwargs)

    # Read back from the stored model rather than echoing the input: phi and mu
    # are two views of the same thing (mu = tan(phi)), and MohrCoulomb derives
    # whichever was not given. Printing only what was typed hid the other one —
    # and mu is what the solvers actually use.
    law = problem.contact_properties.contact_model
    print(f"Contact law set: MohrCoulomb  phi = {law.phi:.3f} deg  mu = {law.mu:.4f}  c = {law.c}  t_c = {law.t_c}")


def set_joint_model(problem):
    options = Options("Joint model")
    options.add_number("kn", 1e9, minimum=0.0, keyword="NormalStiffness", units="N/m", prompt="Normal stiffness kn")
    options.add_number("kt", 1e9, minimum=0.0, keyword="TangentialStiffness", units="N/m", prompt="Tangential stiffness kt")

    values = options.get()
    if values is None:
        return

    problem.set_joint_model(values["kn"], values["kt"])
    print(f"Joint model set: kn={values['kn']}, kt={values['kt']}")


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.model
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to set the contact law on", keywords=True)
    if name is None:
        return
    problem = session.problems[name]

    option = choose("Problem_contactlaw", ["ContactLaw", "JointModel"], default="ContactLaw")
    if option is None:
        return

    # `set_contact_law` / `set_joint_model` prompt further and may be cancelled,
    # so this can fire for a command that changes nothing — at most one extra
    # snapshot per session, since `ensure_baseline` is a no-op after the first.
    session.ensure_baseline()

    if option == "ContactLaw":
        set_contact_law(problem)
    elif option == "JointModel":
        set_joint_model(problem)

    session.save_analysis()
    session.record(f"{name}: {option}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
