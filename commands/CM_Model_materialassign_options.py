#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Model_materialassign_options — RhinoCommon variant of Model_materialassign.

Material and target are picked in a single prompt: the material is a cycling
list option (labels sanitized into keywords) and the target an All/Selected
toggle, instead of two sequential rs.GetString calls over printed indices.
"""

import pathlib

import compas_rhino.objects
from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_masonry.inputs import Options
from compas_masonry.inputs import unique_keywords
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

    # Command option values must be single words, so the readable labels are
    # printed and the options carry sanitized (unique) keywords in the same order.
    for i, m in enumerate(materials):
        print(f"{i}: {material_label(m)}")

    keywords = unique_keywords(material_label(m) for m in materials)

    options = Options("Assign material")
    options.add_list("material", keywords, keyword="Material")
    options.add_toggle("target", False, off="All", on="Selected", text=True, keyword="AssignTo")

    values = options.get()
    if values is None:
        return

    material = materials[keywords.index(values["material"])]

    if values["target"] == "All":
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
