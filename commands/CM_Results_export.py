#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Results_export — write stored result sets to a file.

Two formats, because they answer different questions:

- **Json** — `compas.json_dump` of the `Results` objects themselves. `Results`
  is a compas `Data`, so this round-trips exactly and can be loaded back with
  `compas.json_load` for scripting or comparison. Solving is not cheap; this is
  how a run outlives the session.
- **Csv** — one row per contact (resultant, magnitude, stress, opening), for a
  spreadsheet or a plot. Lossy by design: derived numbers only.

Masonry_export writes the *session* — model, problems, boundary conditions —
and deliberately leaves results out, because they are large and reproducible.
This is the counterpart for when you do want to keep them.
"""

import pathlib

from compas_dem.models import BlockModel
from compas_masonry.inputs import choose
from compas_masonry.results import contact_openings
from compas_masonry.results import contact_resultants
from compas_masonry.results import face_stresses
from compas_masonry.results import summary
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn
from compas_rui.forms import FileForm

import compas
import rhinoscriptsyntax as rs  # type: ignore


def choose_results(session, problem_name):
    """Pick one or more stored result sets. Returns {key: results} or None."""
    stored = (session.get("results") or {}).get(problem_name) or {}
    if not stored:
        warn(f"No results stored for {problem_name}. Run Problem_solve first.")
        return None

    keys = sorted(stored)
    if len(keys) == 1:
        return {keys[0]: stored[keys[0]]}

    picked = rs.MultiListBox(keys, message="Result set(s) to export", title="Results")
    if not picked:
        return None
    return {key: stored[key] for key in picked}


def export_json(selected, problem_name, model, filepath) -> None:
    """Dump the Results objects, with enough context to make sense of them later."""
    data = {
        "problem": problem_name,
        "model_id": str(model.guid),
        "results": selected,
        "summary": {key: summary(results, model) for key, results in selected.items()},
    }
    compas.json_dump(data, filepath)


def export_csv(selected, filepath) -> None:
    """One row per contact, across every selected result set."""
    lines = ["result,contact,fx,fy,fz,magnitude,stress,opening"]
    for key, results in selected.items():
        stresses = {label: value for value, _, label in face_stresses(results)}
        openings = {label: value for value, _, label in contact_openings(results)}
        for _, vector, magnitude, edge in sorted(contact_resultants(results), key=lambda row: -row[2]):
            label = f"{edge[0]}-{edge[1]}"
            stress = stresses.get(label)
            opening = openings.get(label)
            lines.append(
                f"{key},{label},{vector[0]:.10g},{vector[1]:.10g},{vector[2]:.10g},{magnitude:.10g},"
                f"{'' if stress is None else format(stress, '.10g')},"
                f"{'' if opening is None else format(opening, '.10g')}"
            )

    pathlib.Path(filepath).write_text("\n".join(lines) + "\n")
    return len(lines) - 1


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")
    if not session.problems:
        return warn("No problem in session. Run Problem_create first.")

    name = session.choose_problem(message="Problem to export results from", keywords=True)
    if name is None:
        return

    selected = choose_results(session, name)
    if not selected:
        return

    fmt = choose("Format", ["Json", "Csv"], default="Json")
    if fmt is None:
        return

    basedir = session.basedir or pathlib.Path().home()
    suffix = "json" if fmt == "Json" else "csv"
    default = f"{name}_results.{suffix}"

    filepath = FileForm.save(str(basedir), default)
    if not filepath:
        return

    try:
        if fmt == "Json":
            export_json(selected, name, model, filepath)
            print(f"Exported {len(selected)} result set(s) to {filepath}")
            print("Load it back with compas.json_load; the Results objects round-trip exactly.")
        else:
            rows = export_csv(selected, filepath)
            print(f"Exported {rows} contact row(s) from {len(selected)} result set(s) to {filepath}")
    except Exception as e:
        return warn(f"Export failed: {e}")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
