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

# `FormDiagram` is registered by compas_tna too, under the SAME key and the same
# "Rhino" context. Registration is a plain dict assignment —
# `ITEM_SCENEOBJECT[context][item_type] = sceneobject_type` — so the last plugin
# discovered wins, silently, and nothing here controls that order. compas_tna is a
# hard dependency of ours, so this fires with no other plugin installed.
#
# RhinoVAULT does NOT collide directly: it registers its own subclasses
# (`compas_rv.datastructures.FormDiagram`, `Pattern`, `ThrustDiagram`, `ForceDiagram`),
# which are different type objects and therefore different keys. Lookup walks the MRO,
# so an RV diagram finds RV's exact-type entry first. RV only adds another compas_tna
# registrant to the key we already contend for.
#
# `Block`, `FrictionContact` and `InteractionGraph` have no other registrant under
# "Rhino". (compas_model registers `Element -> ElementObject` with NO context, which
# lands in a different dict; Rhino lookups only search ITEM_SCENEOBJECT["Rhino"].)
#
# So the exposure is exactly one type, reached only by the four TNA_* commands, and it
# fails silently — wrong colours, wrong layers, no error. Options and symptoms:
# temp/status_open_decisions.md §7.9.


@plugin(category="factories", pluggable_name="register_scene_objects", requires=["Rhino"])
def register_scene_objects_rhino():
    register(FormDiagram, RhinoFormDiagramObject, context="Rhino")
    register(Block, RhinoBlockObject, context="Rhino")
    register(InteractionGraph, RhinoInteractionGraphObject, context="Rhino")
    register(FrictionContact, RhinoContactObject, context="Rhino")
