#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Model_materialassign — assign a stored material to blocks (All / Selected).

Materials are created/managed by the Model_material command. Here we only
attach an existing model Material to block elements. Selected blocks are
resolved via the same guid->node tag scheme as Model_supports
(session.guid_element_map / find_node). session.redraw() then writes the
"material_guid" User Text tag onto each affected block.
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

import compas_rhino.objects
from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def material_label(material) -> str:
    return f"{material.name} ({material.__class__.__name__})"


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    materials = list(model.materials())
    if not materials:
        return warn("No materials in the model yet. Run Model_material > Create first.")

    # rs.GetString option keywords can't contain spaces/parens, so the
    # selectable tokens are plain indices; print the readable labels above it.
    for i, m in enumerate(materials):
        print(f"{i}: {material_label(m)}")

    indices = [str(i) for i in range(len(materials))]
    index = rs.GetString(message="Material index to assign", strings=indices)
    if not index:
        return
    material = materials[int(index)]

    target = rs.GetString(message="Assign to", strings=["All", "Selected"])
    if not target:
        return

    if target == "All":
        elements = [block for block in model.elements() if isinstance(block, Block)]
    else:
        guids = compas_rhino.objects.select_objects(message="Select blocks to assign the material to")
        if not guids:
            return
        guid_element_map = session.guid_element_map(model)
        nodes = {n for n in (session.find_node(g, guid_element_map) for g in guids) if n is not None}
        elements = [model.graph.node_element(n) for n in nodes]

    if not elements:
        return warn("No blocks resolved from the selection.")

    model.assign_material(material, elements=elements)
    session["blockmodel"] = model
    session.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
