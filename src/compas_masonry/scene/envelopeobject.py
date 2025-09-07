from typing import Optional

import scriptcontext as sc  # type: ignore

from compas.colors import Color
from compas.datastructures import Mesh
from compas.scene.descriptors.color import ColorAttribute
from compas_masonry.session import MasonrySession as Session
from compas_rhino.conversions import transformation_to_rhino
from compas_rhino.conversions import vertices_and_faces_to_rhino
from compas_rhino.scene import RhinoSceneObject
from compas_tna.envelope import Envelope


class RhinoEnvelopeObject(RhinoSceneObject):
    session: Session = Session()

    color = ColorAttribute(default=Color.black())

    def __init__(
        self,
        color: Optional[Color] = None,
        show_intrados=True,
        show_middle=False,
        show_extrados=True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.color = color or self.color
        self.show_intrados = show_intrados
        self.show_middle = show_middle
        self.show_extrados = show_extrados

    @property
    def settings(self) -> dict:
        settings = super().settings
        settings["color"] = self.color
        settings["show_intrados"] = self.show_intrados
        settings["show_middle"] = self.show_middle
        settings["show_extrados"] = self.show_extrados
        return settings

    @property
    def envelope(self) -> Envelope:
        return self.item  # type: ignore

    @envelope.setter
    def envelope(self, envelope: Envelope) -> None:
        self._item = envelope
        self._transformation = None

    def draw(self):
        self._guids = []

        if self.show_intrados:
            self.draw_intrados()

        if self.show_middle:
            self.draw_middle()

        if self.show_extrados:
            self.draw_extrados()

        return self._guids

    def _draw_mesh(self, mesh: Mesh, name: str) -> None:
        attr = self.compile_attributes(name=name, color=self.color)
        vertex_index = mesh.vertex_index()
        vertices = [mesh.vertex_attributes(vertex, "xyz") for vertex in mesh.vertices()]
        faces = [[vertex_index[vertex] for vertex in mesh.face_vertices(face)] for face in mesh.faces()]
        geometry = vertices_and_faces_to_rhino(vertices, faces, color=self.color, disjoint=True)
        geometry.Transform(transformation_to_rhino(self.worldtransformation))
        guid = sc.doc.Objects.AddMesh(geometry, attr)
        if self.group:
            self.add_to_group(self.group, [guid])
        return guid

    def draw_intrados(self):
        if not self.envelope.intrados:  # type: ignore
            return
        guid = self._draw_mesh(self.envelope.intrados, name="Intrados")  # type: ignore
        self._guids.append(guid)

    def draw_middle(self):
        if not self.envelope.middle:  # type: ignore
            return
        guid = self._draw_mesh(self.envelope.middle, name="Middle")  # type: ignore
        self._guids.append(guid)

    def draw_extrados(self):
        if not self.envelope.extrados:  # type: ignore
            return
        guid = self._draw_mesh(self.envelope.extrados, name="Extrados")  # type: ignore
        self._guids.append(guid)
