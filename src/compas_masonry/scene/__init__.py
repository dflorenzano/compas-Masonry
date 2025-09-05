from compas.plugins import plugin
from compas.scene.context import register

from compas_tna.diagrams import FormDiagram
from .formobject import RhinoFormDiagramObject


# this might clash with RV
@plugin(category="factories", pluggable_name="register_scene_objects", requires=["Rhino"])
def register_scene_objects_rhino():
    register(FormDiagram, RhinoFormDiagramObject, context="Rhino")
