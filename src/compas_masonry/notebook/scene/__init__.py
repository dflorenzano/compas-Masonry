from compas.plugins import plugin
from compas.scene import register

from .blockobject import ThreeBlockObject


@plugin(category="factories", requires=["pythreejs"])
def register_scene_objects():
    pass
