#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.7

"""Model_material — manage the materials stored on the session BlockModel.

Operations: Create / Modify / Remove / Clear / Duplicate. Assignment of a
material to blocks lives in a separate command (Model_materialassign) to keep
each file focused.

Materials are compas_dem `Stone` / `GenericMaterial` (both inherit from
compas_model `Material`, carry a persistent `.guid`). They live on
`model._materials`; assignment to a block is stored on the block element and
surfaced in Rhino as a "material_guid" User Text tag written by
session.redraw() (see session._tag_block_materials).
"""

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_dem.material import GenericMaterial
from compas_dem.material import Stone
from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn

MATERIAL_TYPES = {"Stone": Stone, "Generic": GenericMaterial}

# Properties prompted for a custom material. fc/ft/Ecm accept 0 to mean "unset"
# (None) since rs.GetReal can't return None directly.
NULLABLE = ("fc", "ft", "Ecm")


def material_label(material) -> str:
    return f"{material.name} ({material.__class__.__name__})"


def print_materials(materials) -> None:
    for i, m in enumerate(materials):
        print(f"{i}: {material_label(m)}")


def pick_material(materials, message="Material index"):
    """Print the materials with their index, then prompt for one by index."""
    print_materials(materials)
    indices = [str(i) for i in range(len(materials))]
    index = rs.GetString(message=message, strings=indices)
    if not index:
        return None
    return materials[int(index)]


def prompt_properties(defaults):
    """Prompt for the custom material properties, seeded with `defaults`.

    Returns a dict of {name, fc, ft, Ecm, density, poisson} or None if cancelled.
    """
    name = rs.GetString(message="Name", defaultString=defaults.get("name") or "Material")
    if name is None:
        return None
    fc = rs.GetReal(message="Compressive strength fc [MPa] (0 = unset)", number=defaults.get("fc") or 0.0, minimum=0.0)
    if fc is None:
        return None
    ft = rs.GetReal(message="Tensile strength ft [MPa] (0 = derive from fc)", number=defaults.get("ft") or 0.0, minimum=0.0)
    if ft is None:
        return None
    Ecm = rs.GetReal(message="Modulus of elasticity Ecm [GPa] (0 = unset)", number=defaults.get("Ecm") or 0.0, minimum=0.0)
    if Ecm is None:
        return None
    density = rs.GetReal(message="Density [kg/m3]", number=defaults.get("density") or 2400.0, minimum=0.0)
    if density is None:
        return None
    poisson = rs.GetReal(message="Poisson's ratio", number=defaults.get("poisson") or 0.2, minimum=0.0)
    if poisson is None:
        return None
    return {
        "name": name,
        "fc": fc or None,
        "ft": ft or None,
        "Ecm": Ecm or None,
        "density": density,
        "poisson": poisson,
    }


def material_properties(material) -> dict:
    """Extract the editable properties of an existing material as a dict."""
    return {
        "name": material.name,
        "fc": material.fc,
        "ft": material.ft,
        "Ecm": material.Ecm,
        "density": material.density,
        "poisson": material.poisson,
    }


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    model: BlockModel = session.get("blockmodel")
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    option = rs.GetString(message="Model_material", strings=["Create", "Modify", "Remove", "Clear", "Duplicate"])
    if not option:
        return

    # =============================================================================
    # Create
    # =============================================================================

    if option == "Create":
        kind = rs.GetString(message="Material type", strings=list(MATERIAL_TYPES.keys()))
        if not kind:
            return
        cls = MATERIAL_TYPES[kind]

        source = rs.GetString(message="Source", strings=["Predefined", "Custom"])
        if not source:
            return

        if source == "Predefined":
            key = rs.GetString(message="Predefined material", strings=list(cls.predefined_material.keys()))
            if not key:
                return
            material = cls.from_predefined_material(key)
        else:
            props = prompt_properties({})
            if props is None:
                return
            material = cls(**props)

        model.add_material(material)
        print(f"Added material: {material_label(material)}")

    # =============================================================================
    # Modify (mutates in place, so existing block assignments stay valid)
    # =============================================================================

    elif option == "Modify":
        materials = list(model.materials())
        if not materials:
            return warn("No materials in the model yet. Run Model_material > Create first.")

        material = pick_material(materials, message="Material index to modify")
        if material is None:
            return

        props = prompt_properties(material_properties(material))
        if props is None:
            return

        material.name = props["name"]
        material.fc = props["fc"]
        material.ft = props["ft"]
        material.Ecm = props["Ecm"]
        material.density = props["density"]
        material.poisson = props["poisson"]
        print(f"Modified material: {material_label(material)}")

    # =============================================================================
    # Remove (drop from model, unassign from any blocks that referenced it)
    # =============================================================================

    elif option == "Remove":
        materials = list(model.materials())
        if not materials:
            return warn("No materials in the model to remove.")

        material = pick_material(materials, message="Material index to remove")
        if material is None:
            return

        guid = str(material.guid)
        for element in model.elements():
            if element._material == guid:
                element._material = None
        model._materials.pop(guid, None)
        print(f"Removed material: {material_label(material)}")
        session.redraw()

    # =============================================================================
    # Clear (remove every material and unassign all blocks)
    # =============================================================================

    elif option == "Clear":
        if not list(model.materials()):
            return warn("No materials in the model to clear.")

        confirm = rs.GetString(message="Clear ALL materials?", strings=["Yes", "No"])
        if confirm != "Yes":
            return

        for element in model.elements():
            element._material = None
        model._materials.clear()
        print("Cleared all materials.")
        session.redraw()

    # =============================================================================
    # Duplicate (same type, copied properties, ' copy' suffix)
    # =============================================================================

    elif option == "Duplicate":
        materials = list(model.materials())
        if not materials:
            return warn("No materials in the model to duplicate.")

        material = pick_material(materials, message="Material index to duplicate")
        if material is None:
            return

        props = material_properties(material)
        props["name"] = f"{props['name']} copy"
        duplicate = type(material)(**props)
        model.add_material(duplicate)
        print(f"Duplicated material: {material_label(duplicate)}")

    # Persist the mutated model so the change survives to the next command.
    session["blockmodel"] = model


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
