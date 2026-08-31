from compas.plugins import plugin
from compas.scene.context import register

from compas_tna.diagrams import FormDiagram
from compas_dem.elements import Block
from compas_dem.interactions import FrictionContact
from compas_model.models import InteractionGraph
from .blockobject import RhinoBlockObject
from .contactobject import RhinoContactObject
from .formobject import RhinoFormDiagramObject
from .igraphobject import RhinoInteractionGraphObject

# this clashes with TNA and/or RV
# we need a strategy for this


@plugin(category="factories", pluggable_name="register_scene_objects", requires=["Rhino"])
def register_scene_objects_rhino():
    register(FormDiagram, RhinoFormDiagramObject, context="Rhino")
    register(Block, RhinoBlockObject, context="Rhino")
    register(InteractionGraph, RhinoInteractionGraphObject, context="Rhino")
    register(FrictionContact, RhinoContactObject, context="Rhino")
