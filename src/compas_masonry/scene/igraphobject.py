import scriptcontext as sc  # type: ignore

import compas_rhino.conversions
from compas.colors import Color
from compas.geometry import Line
from compas.scene.descriptors.color import ColorAttribute
from compas_dem.elements import Block
from compas_masonry.session import MasonrySession as Session
from compas_model.models import InteractionGraph
from compas_rhino.scene import RhinoSceneObject


class RhinoInteractionGraphObject(RhinoSceneObject):
    """Class for representing a block in a Rhino scene."""

    session: Session = Session()

    nodecolor = ColorAttribute(default=Color.cyan())
    edgecolor = ColorAttribute(default=Color.cyan())

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

    @property
    def graph(self) -> InteractionGraph:
        """The COMPAS DEM InteractionGraph element.

        Returns
        -------
        :class:`compas_model.models.InteractionGraph`

        """
        return self.item  # type: ignore

    @graph.setter
    def graph(self, graph: InteractionGraph) -> None:
        self.item = graph  # type: ignore

    def draw(self) -> list[str]:
        """Draw the interaction graph in Rhino.

        Returns
        -------
        list[str]
            A list of GUIDs of the drawn objects.

        """
        guids = []

        node_point = {}

        element: Block
        for node in self.graph.nodes():
            element = self.graph.node_element(node)  # type: ignore
            node_point[node] = element.point

            geometry = compas_rhino.conversions.point_to_rhino(element.point)
            attr = self.compile_attributes(name="Block_{}".format(node), color=self.nodecolor)
            guid = sc.doc.Objects.AddPoint(geometry, attr)
            guids.append(guid)

        for u, v in self.graph.edges():
            line = Line(node_point[u], node_point[v])
            geometry = compas_rhino.conversions.line_to_rhino(line)
            attr = self.compile_attributes(name="Interaction_{}_{}".format(u, v), color=self.edgecolor)
            guid = sc.doc.Objects.AddLine(geometry, attr)
            guids.append(guid)

        if self.group:
            self.add_to_group(self.group, guids)

        self._guids = guids
        return guids
