#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Session_import — open a session saved by Session_save.

Saving and loading work the way RhinoVAULT's do: one command opens a session,
one saves it. The per-artefact import commands this replaced (Model_import,
Model_export, Problem_export) are gone.

Replaces the current session state: the `Analysis` — model plus every problem
with its boundary conditions — is read back as one object, the active problem is
restored, the model is drawn and the boundary condition layers are regenerated.

Files written before 2026-08-07 held `blockmodel` and `problems` as separate
keys, against a compas_dem boundary-condition API that has since been reverted.
They are refused with a message rather than half-imported.

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

    if not isinstance(data, dict):
        return warn(f"This is not a COMPAS Masonry session file: {filepath}")

    if "analysis" not in data:
        if "blockmodel" in data:
            # Deliberately refused rather than translated. A pre-2026-08-07 file
            # carries `blockmodel` + `problems` written against the compas_dem API
            # that was reverted — its boundary conditions are the flat, typed kind
            # with different attribute names, so the objects inside would not
            # deserialize into anything this plugin can draw or solve.
            return warn("This session file predates 2026-08-07 and cannot be opened. Rebuild the model and problems, then save again.")
        return warn("This is not a COMPAS Masonry session file — it holds no analysis.")

    analysis = data["analysis"]
    model = analysis.model
    problems = {problem.name: problem for problem in analysis.problems}

    if session.model is not None or session.problems:
        if not confirm("Importing replaces the current model and all its problems. Continue?"):
            return

    # after the last bail-out, before the first change — an import replaces
    # everything, so the state it replaced is exactly what undo is for
    session.ensure_baseline()

    # clear_model drops the whole analysis (model, problems) and the results with
    # it; the imported analysis then replaces it wholesale. No rebinding: the
    # problems came out of `Analysis.__from_data__` with their model already
    # loaded, which is the reason the file holds one object rather than two.
    session.clear_model()
    session["analysis"] = analysis
    if model is not None:
        session.draw_model()

    active = data.get("active_problem")
    if active in problems:
        session.set_active_problem(active)

    restore_settings(session, data.get("settings"))

    for name in problems:
        session.ensure_indexed_problem_layer(name)
        session.draw_problem_conditions(name, model)

    rs.Redraw()

    print(f"Imported session from {filepath}")
    print(f"  blockmodel: {'yes' if model is not None else 'no'}")
    print(f"  problems  : {len(problems)} ({', '.join(problems) or '-'})")
    print("Results are not part of the file — re-run Problem_solve.")
    session.record(f"Import: {pathlib.Path(filepath).name}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
