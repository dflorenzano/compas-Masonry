import scriptcontext as sc  # type: ignore

import compas_rhino.conversions
from compas.colors import Color
from compas.datastructures import Mesh
from compas.scene.descriptors.color import ColorAttribute
from compas_dem.interactions import FrictionContact
from compas_masonry.session import MasonrySession as Session
from compas_rhino.scene import RhinoSceneObject


class RhinoContactObject(RhinoSceneObject):
    """Class for representing a block-block contact in a Rhino scene."""

    session: Session = Session()

    defaultcolor = ColorAttribute(default=Color.cyan())
    supportcolor = ColorAttribute(default=Color.red())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def contact(self) -> FrictionContact:
        """The COMPAS DEM Contact element.

        Returns
        -------
        :class:`compas_dem.interactions.FrictionContact`

        """
        return self.item  # type: ignore

    @contact.setter
    def contact(self, contact: FrictionContact) -> None:
        self.item = contact  # type: ignore

    def draw(self) -> list[str]:
        """Draw the contact in Rhino.

        Returns
        -------
        list[str]
            A list of GUIDs of the drawn objects.

        """
        guids = []

        mesh: Mesh = self.contact.mesh  # type: ignore

        color = self.defaultcolor
        geometry = compas_rhino.conversions.mesh_to_rhino(mesh)
        attr = self.compile_attributes(name=self.name, color=color)
        guid = sc.doc.Objects.AddMesh(geometry, attr)
        guids.append(guid)

        if self.group:
            self.add_to_group(self.group, guids)

        self._guids = guids
        return guids
