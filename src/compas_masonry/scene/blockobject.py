import scriptcontext as sc  # type: ignore

import compas_rhino.conversions
from compas.colors import Color
from compas.datastructures import Mesh
from compas.scene.descriptors.color import ColorAttribute
from compas_dem.elements import Block
from compas_masonry.session import MasonrySession as Session
from compas_rhino.scene import RhinoSceneObject


class RhinoBlockObject(RhinoSceneObject):
    """Class for representing a block in a Rhino scene."""

    session: Session = Session()

    defaultcolor = ColorAttribute(default=Color.grey().lightened(50))
    supportcolor = ColorAttribute(default=Color.red())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def block(self) -> Block:
        """The COMPAS DEM Block element.

        Returns
        -------
        :class:`compas_dem.elements.Block`

        """
        return self.item  # type: ignore

    @block.setter
    def block(self, block: Block) -> None:
        self.item = block  # type: ignore

    def draw(self) -> list[str]:
        """Draw the block in Rhino.

        Returns
        -------
        list[str]
            A list of GUIDs of the drawn objects.

        """
        guids = []

        mesh: Mesh = self.block.modelgeometry  # type: ignore

        color = self.supportcolor if self.block.is_support else self.defaultcolor

        # ALWAYS a mesh, one object per block. There used to be a `show_wireframe`
        # branch here that drew one line per edge instead; it was deleted on
        # 2026-08-20 because a wireframe LOOK is a Rhino viewport display mode,
        # not a different set of objects. Drawing lines gave the same picture
        # while emptying the document of the geometry everything else depends on:
        # sub-object face/vertex picking had nothing to pick, and the guid
        # tagging that `find_node` and `guid_element_map` walk assumes one object
        # per block. See `settings.blockmodel.results_display_mode`.
        geometry = compas_rhino.conversions.mesh_to_rhino(mesh)
        attr = self.compile_attributes(name=self.name, color=color)
        guid = sc.doc.Objects.AddMesh(geometry, attr)
        guids.append(guid)

        self._guids = guids
        return guids
