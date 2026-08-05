#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Session_import — open a session saved by Session_save.

Saving and loading work the way RhinoVAULT's do: one command opens a session,
one saves it. The per-artefact import commands this replaced (Model_import,
Model_export, Problem_export) are gone.

Replaces the current session state: the model and every problem (with its
boundary conditions) are read back, the active problem is restored, the model is
drawn and the boundary condition layers are regenerated.

Destructive by nature — it clears the current model and its problems — so it
asks for confirmation first.
"""

import pathlib

import compas
import rhinoscriptsyntax as rs  # type: ignore
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm
from compas_rui.feedback import warn
from compas_rui.forms import FileForm


def restore_settings(session, settings) -> None:
    """Apply exported settings section by section, ignoring unknown keys."""
    if not isinstance(settings, dict):
        return
    for section, values in settings.items():
        target = getattr(session.settings, section, None)
        if target is None or not isinstance(values, dict):
            continue
        for key, value in values.items():
            try:
                setattr(target, key, value)
            except Exception:
                pass  # a setting that no longer exists or no longer validates


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    path = rs.DocumentPath()  # to make sure the document has a path
    basedir = pathlib.Path(path).parent if path else pathlib.Path().home()

    filepath = FileForm.open(str(basedir))
    if not filepath:
        return

    try:
        data = compas.json_load(filepath)
    except Exception as e:
        return warn(f"Could not read {filepath}: {e}")

    if not isinstance(data, dict) or "blockmodel" not in data:
        return warn("This is not a COMPAS Masonry session file — it holds no blockmodel and no problems.")

    if session.get("blockmodel") is not None or session.problems:
        if not confirm("Importing replaces the current model and all its problems. Continue?"):
            return

    model = data.get("blockmodel")
    problems = data.get("problems") or {}

    # set_model clears the model, its problems and its results, and redraws
    session.clear_model()
    if model is not None:
        session.set_model(model)

    for name, problem in problems.items():
        session.problems[name] = problem
    session.save_problems()

    active = data.get("active_problem")
    if active in problems:
        session.set_active_problem(active)

    restore_settings(session, data.get("settings"))

    for name in problems:
        session.ensure_indexed_problem_layer(name)
        session.draw_problem_bcs(name, model)

    rs.Redraw()

    print(f"Imported session from {filepath}")
    print(f"  blockmodel: {'yes' if model is not None else 'no'}")
    print(f"  problems  : {len(problems)} ({', '.join(problems) or '-'})")
    print("Results are not part of the file — re-run Problem_solve.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
