from compas.plugins import plugin
from compas.scene.context import register

from compas_tna.diagrams import FormDiagram
from .formobject import RhinoFormDiagramObject

# this clashes with TNA and/or RV
# we need a strategy for this


@plugin(category="factories", pluggable_name="register_scene_objects", requires=["Rhino"])
def register_scene_objects_rhino():
    register(FormDiagram, RhinoFormDiagramObject, context="Rhino")
