from compas.plugins import plugin
from compas.scene import register

from .blockobject import BlockObject


@plugin(category="factories")
def register_scene_objects():
    pass


__all__ = []
