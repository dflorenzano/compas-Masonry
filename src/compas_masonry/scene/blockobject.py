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

    def __init__(self, show_wireframe=False, **kwargs):
        super().__init__(**kwargs)
        self.show_wireframe = show_wireframe

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

        if self.session.settings.blockmodel.show_wireframe:
            for edge in mesh.edges():
                line = mesh.edge_line(edge)
                geometry = compas_rhino.conversions.line_to_rhino(line)
                attr = self.compile_attributes(name=self.name, color=color)
                guid = sc.doc.Objects.AddLine(geometry, attr)
                guids.append(guid)
                self.add_to_group(self.group, guids)
        else:
            geometry = compas_rhino.conversions.mesh_to_rhino(mesh)
            attr = self.compile_attributes(name=self.name, color=color)
            guid = sc.doc.Objects.AddMesh(geometry, attr)
            guids.append(guid)

        self._guids = guids
        return guids
