#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Model_supports_options — RhinoCommon variant of Model_supports.

Only the Add/Remove/Clear pick changes (command line options instead of
rs.GetString); the support logic is identical. See Model_supports for why
guids are resolved to graph nodes before any redraw.

Supports are copied onto each Problem when it is created, and into each
BoundaryCondition when it is registered — so editing them here leaves every
existing problem holding the old set. Rather than let that drift silently, this
offers to push the new set into the problems (the same thing
Problem_create > RefreshSupports does).
"""

import pathlib

import compas_rhino.objects
from compas_dem.models import BlockModel
from compas_masonry.inputs import choose
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm
from compas_rui.feedback import warn


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    option = choose("Supports", ["Add", "Remove", "Clear"])
    if option is None:
        return

    guid_element_map = session.guid_element_map(model)

    if option in ("Add", "Remove"):
        verb = "add" if option == "Add" else "remove"
        guids = compas_rhino.objects.select_objects(message=f"Select supports you want to {verb}")
        if not guids:
            return
        nodes = {n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None}
        if not nodes:
            return warn("No blocks resolved from the selection.")
        for node in nodes:
            model.graph.node_element(node).is_support = option == "Add"
        print(f"{option}: {len(nodes)} support(s).")

    elif option == "Clear":
        for node in model.graph.nodes():
            model.graph.node_element(node).is_support = False
        print("Cleared all supports.")

    session["blockmodel"] = model
    session.sync_support_layers()
    session.redraw()

    refresh_problems(session, model)


def refresh_problems(session, model) -> None:
    """Offer to re-import the new supports into every existing problem."""
    if not session.problems:
        return

    stale = []
    current = sorted(block.graphnode for block in model.elements() if block.is_support)
    for name, problem in session.problems.items():
        if sorted(problem.supports) != current:
            stale.append(name)

    if not stale:
        return

    print(f"{len(stale)} problem(s) still hold the previous supports: {', '.join(stale)}")
    if not confirm("Refresh the supports on them? (prescribed displacements are kept)"):
        print("Left unchanged. Run Problem_create > RefreshSupports later to apply them.")
        return

    for name in stale:
        before, after = session.refresh_problem_supports(name, model)
        print(f"  {name}: {len(before)} -> {len(after)} support(s).")
        session.draw_problem_bcs(name, model)


if __name__ == "__main__":
    RunCommand()
