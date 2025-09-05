import math

from compas_viewer.config import Config
from compas_viewer.config import MenubarConfig
from compas_viewer.scene import ViewerSceneObject
from compas_viewer.viewer import Viewer

from compas.colors import Color
from compas.geometry import Cylinder
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Vector
from compas.geometry import bounding_box_xy
from compas.scene import Group

config = Config()


def show_blocks():
    from compas_viewer import Viewer

    viewer: MasonryViewer = Viewer()  # type: ignore

    viewer.groups["supports"].show = True
    viewer.groups["blocks"].show = True
    viewer.groups["contacts"].show = False
    viewer.groups["interactions"].show = False

    obj: ViewerSceneObject

    for obj in viewer.groups["supports"].children:
        obj.show_faces = True
        obj.update()

    for obj in viewer.groups["blocks"].children:
        obj.show_faces = True
        obj.update()

    viewer.ui.sidebar.update()
    viewer.renderer.update()


def show_contacts():
    from compas_viewer import Viewer

    viewer: MasonryViewer = Viewer()  # type: ignore

    viewer.groups["supports"].show = True
    viewer.groups["blocks"].show = True
    viewer.groups["contacts"].show = True
    viewer.groups["interactions"].show = False

    obj: ViewerSceneObject

    for obj in viewer.groups["supports"].children:
        obj.show_faces = False
        obj.update()

    for obj in viewer.groups["blocks"].children:
        obj.show_faces = False
        obj.update()

    viewer.ui.sidebar.update()
    viewer.renderer.update()


def show_interactions():
    from compas_viewer import Viewer

    viewer: MasonryViewer = Viewer()  # type: ignore

    viewer.groups["supports"].show = True
    viewer.groups["blocks"].show = True
    viewer.groups["contacts"].show = False
    viewer.groups["interactions"].show = True

    obj: ViewerSceneObject

    for obj in viewer.groups["supports"].children:
        obj.show_faces = False
        obj.update()

    for obj in viewer.groups["blocks"].children:
        obj.show_faces = False
        obj.update()

    viewer.ui.sidebar.update()
    viewer.renderer.update()


def show_intrados_extrados():
    from compas_viewer import Viewer

    viewer: MasonryViewer = Viewer()  # type: ignore

    viewer.groups["intrados"].show = True
    viewer.groups["extrados"].show = True

    viewer.ui.sidebar.update()
    viewer.renderer.update()


MenubarConfig._items.append(
    {
        "title": "COMPAS TNO",
        "items": [
            {
                "title": "Show Intrados/Extrados",
                "action": show_intrados_extrados,
            },
        ],
    }
)


class MasonryViewer(Viewer):
    blockcolor: Color = Color.grey().lightened(85)
    supportcolor: Color = Color.red().lightened(50)
    interfacecolor: Color = Color.cyan().lightened(50)
    graphnodecolor: Color = Color.blue()
    graphedgecolor: Color = Color.blue().lightened(50)
    surfacecolor: Color = Color.grey().lightened(90)

    form_max_thk: float = 0.08  # Maximum pipe radius for the largest detected force
    intrados_color: Color = Color.blue().darkened(30)
    extrados_color: Color = Color.green().darkened(30)
    form_color: Color = Color.red()
    shape_color: Color = Color.grey().lightened(30)
    shape_opacity: float = 0.4
    thrust_opacity: float = 0.9
    crack_opacity: float = 0.9
    crack_size: int = 20  # Size of crack points
    cracks_tol: float = 1e-3  # Tolerance for comparing vertex z to lb/ub values
    surface_linewidth: float = 0.2
    reaction_scale: float = 1.0  # Scale factor for reaction force arrows
    reaction_color: Color = Color.orange()
    reaction_opacity: float = 0.8

    def __init__(self, blockmodel=None, formdiagram=None, envelope=None, config=config):
        super().__init__(config=config)
        self.blockmodel = blockmodel
        self.envelope = envelope
        self.formdiagram = formdiagram
        self.groups = {}

    def setup(self):
        if self.blockmodel is not None:
            self.setup_blockmodel()
            self.add_supports()
            self.add_blocks()
            self.add_contacts()
            self.add_graph()

        if self.envelope is not None:
            self.setup_envelope()
            self.add_envelope()

        if self.formdiagram is not None:
            self.setup_formdiagram()
            self.add_form()
            self.add_cracks()
            self.add_reactions()
            self.add_formdiagram_supports()
            self.add_evelope_limits()
            self.add_selfweight_arrows()

    # =============================================================================
    # Add elements
    # =============================================================================

    def setup_envelope(self):
        """Add an envelope to the viewer.

        Parameters
        ----------
        envelope : Envelope
            The envelope to add to the viewer.
        """
        if self.envelope is None:
            return

        self.groups["envelope"] = self.scene.add_group(name="Envelope")
        self.groups["intrados"] = self.scene.add_group(name="Intrados", parent=self.groups["envelope"])
        self.groups["extrados"] = self.scene.add_group(name="Extrados", parent=self.groups["envelope"])
        self.groups["middle"] = self.scene.add_group(name="Middle", parent=self.groups["envelope"])
        self.groups["fill"] = self.scene.add_group(name="Fill", parent=self.groups["envelope"])

    def setup_formdiagram(self):
        """Add a form diagram to the viewer.

        Parameters
        ----------
        formdiagram : FormDiagram
            The form diagram to add to the viewer.
        """
        if self.formdiagram is None:
            return

        self.groups["formdiagram"] = self.scene.add_group(name="FormDiagram")
        self.groups["diagram"] = self.scene.add_group(name="Diagram", parent=self.groups["formdiagram"])
        self.groups["TNA supports"] = self.scene.add_group(name="Diagram Supports", parent=self.groups["formdiagram"])
        self.groups["diagram_mesh"] = self.scene.add_group(name="Diagram mesh", parent=self.groups["formdiagram"], show=False)

        self.groups["cracks"] = self.scene.add_group(name="Cracks", parent=self.groups["formdiagram"])
        self.groups["reactions"] = self.scene.add_group(name="Reactions", parent=self.groups["formdiagram"])
        self.groups["selfweight"] = self.scene.add_group(name="Selfweight", parent=self.groups["formdiagram"], show=False)
        self.groups["envelope_limits"] = self.scene.add_group(name="Envelope limits", parent=self.groups["formdiagram"], show=False)

    def setup_blockmodel(self):
        """Add a block model to the viewer.

        Parameters
        ----------
        blockmodel : BlockModel
            The block model to add to the viewer.
        """
        if self.blockmodel is None:
            return

        self.groups["blockmodel"] = self.scene.add_group(name="BlockModel")
        self.groups["supports"] = self.scene.add_group(name="Supports", parent=self.groups["blockmodel"])
        self.groups["blocks"] = self.scene.add_group(name="Blocks", parent=self.groups["blockmodel"])
        self.groups["contacts"] = self.scene.add_group(name="Contacts", parent=self.groups["blockmodel"], show=False)
        self.groups["interactions"] = self.scene.add_group(name="Interactions", parent=self.groups["blockmodel"], show=False)

    # =============================================================================
    # Blocks and Contacts
    # =============================================================================

    def add_supports(self):
        if self.blockmodel is None:
            return

        parent: Group = self.groups["supports"]

        for block in self.blockmodel.supports():
            parent.add(
                block.modelgeometry,
                facecolor=self.supportcolor,  # type: ignore
                edgecolor=self.supportcolor.contrast,
                linewidth=0.5,  # type: ignore
                name=block.name,  # type: ignore
            )

    def add_blocks(self):
        if self.blockmodel is None:
            return

        parent: Group = self.groups["blocks"]

        for block in self.blockmodel.blocks():
            parent.add(
                block.modelgeometry,
                facecolor=self.blockcolor,  # type: ignore
                edgecolor=self.blockcolor.contrast,
                linewidth=0.5,  # type: ignore
                name=block.name,  # type: ignore
            )

    def add_contacts(self):
        if self.blockmodel is None:
            return

        parent: Group = self.groups["contacts"]

        for contact in self.blockmodel.contacts():
            geometry = contact.polygon
            color = self.interfacecolor
            parent.add(geometry, linewidth=1, surfacecolor=color, linecolor=color.contrast)  # type: ignore

    def add_form(self):
        """
        Create and add cylindrical pipes for each form-diagram edge into 'Form' group.

        Parameters
        ----------
        max_thick : float, optional
            Maximum pipe radius for the largest detected force.

        """

        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["diagram"]

        edges = list(formdiagram.edges_where({"_is_edge": True}))
        forces = [formdiagram.edge_attribute(e, "q") * formdiagram.edge_length(e) for e in edges]  # type: ignore
        f_max = math.sqrt(max(abs(max(forces)), abs(min(forces)))) or 1e-6
        for edge in edges:
            q = formdiagram.edge_attribute(edge, "q")
            line = formdiagram.edge_line(edge)
            length = line.length
            force = math.sqrt(abs(q * length))
            if force < 1e-3:
                continue
            radius = (force / f_max) * self.form_max_thk
            cyl = Cylinder.from_line_and_radius(line, radius)
            grp.add(
                cyl,
                name=f"thrust_{edge}",  # type: ignore
                color=self.form_color,  # type: ignore
                opacity=self.thrust_opacity,
            )  # type: ignore

        self.groups["diagram_mesh"].add(formdiagram, show_faces=True, show_lines=True)

    def add_cracks(self):
        """
        Identify vertices where the form touches intrados/extrados and add them to 'Cracks' group.

        Parameters
        ----------
        tol : float, optional
            Tolerance for comparing vertex z to lb/ub values.
        """

        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["cracks"]

        for key in formdiagram.vertices():  # type: ignore
            x, y, z = formdiagram.vertex_coordinates(key)  # type: ignore
            lb = formdiagram.vertex_attribute(key, "lb")  # type: ignore
            ub = formdiagram.vertex_attribute(key, "ub")  # type: ignore
            if lb is not None and abs(z - lb) < self.cracks_tol:
                grp.add(
                    Point(x, y, z),
                    name=f"intrados_crack_{key}",  # type: ignore
                    pointsize=self.crack_size,  # type: ignore
                    pointcolor=self.intrados_color,  # type: ignore
                    opacity=self.crack_opacity,
                )  # type: ignore
            if ub is not None and abs(ub - z) < self.cracks_tol:
                grp.add(
                    Point(x, y, z),
                    name=f"extrados_crack_{key}",  # type: ignore
                    pointsize=self.crack_size,  # type: ignore
                    pointcolor=self.extrados_color,  # type: ignore
                    opacity=self.crack_opacity,
                )  # type: ignore
        self.groups["cracks"] = grp

    def add_reactions(self):
        """
        Create and add reaction force arrows for fixed vertices in the form diagram.
        Reaction forces are stored in the (_rx, _ry, _rz) attributes of vertices.
        """

        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["reactions"]

        # Calculate the diagonal distance of the form diagram
        vertices_xy = [formdiagram.vertex_coordinates(vertex)[:2] for vertex in formdiagram.vertices()]
        bbox = bounding_box_xy(vertices_xy)
        diagonal_distance = math.sqrt((bbox[1][0] - bbox[0][0]) ** 2 + (bbox[1][1] - bbox[0][1]) ** 2)

        # Get all reaction forces to find the maximum for scaling
        reaction_magnitudes = []
        for vertex in formdiagram.vertices():
            rx = formdiagram.vertex_attribute(vertex, "_rx") or 0.0
            ry = formdiagram.vertex_attribute(vertex, "_ry") or 0.0
            rz = formdiagram.vertex_attribute(vertex, "_rz") or 0.0
            magnitude = math.sqrt(rx**2 + ry**2 + rz**2)
            reaction_magnitudes.append(magnitude)

        max_magnitude = max(reaction_magnitudes) if reaction_magnitudes else 1.0

        # Calculate scale so that the longest reaction vector is 1/8 of the diagonal distance
        if max_magnitude > 0:
            target_length = diagonal_distance / 8.0
            self.reaction_scale = target_length / max_magnitude
        else:
            self.reaction_scale = 1.0

        # Add reaction force arrows for fixed vertices
        for vertex in formdiagram.vertices():
            rx = formdiagram.vertex_attribute(vertex, "_rx") or 0.0
            ry = formdiagram.vertex_attribute(vertex, "_ry") or 0.0
            rz = formdiagram.vertex_attribute(vertex, "_rz") or 0.0

            magnitude = math.sqrt(rx**2 + ry**2 + rz**2)

            # Only show reactions with non-zero magnitude
            if magnitude > 1e-6:
                # Get vertex coordinates (support point)
                x, y, z = formdiagram.vertex_coordinates(vertex)

                # Create reaction vector pointing to the support
                reaction_vector = Vector(rx * self.reaction_scale, ry * self.reaction_scale, rz * self.reaction_scale)

                anchor_point = Point(x - rx * self.reaction_scale, y - ry * self.reaction_scale, z - rz * self.reaction_scale)

                # Add the arrow to the group
                grp.add(
                    reaction_vector, anchor=anchor_point, name=f"Reaction_{vertex}_R={magnitude:.1f}", linecolor=self.reaction_color, linewidth=2.0, opacity=self.reaction_opacity
                )

        self.groups["reactions"] = grp

    def add_formdiagram_supports(self):
        """
        Add the supports of the form diagram to the 'TNA supports' group.
        """

        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["TNA supports"]

        supports = formdiagram.vertices_where(is_support=True)
        for vkey in supports:
            x, y, z = formdiagram.vertex_coordinates(vkey)
            grp.add(Point(x, y, z), name=f"TNA support_{vkey}", pointsize=self.crack_size * 1.5, pointcolor=self.supportcolor, opacity=0.95)

        self.groups["TNA supports"] = grp

    def add_bounds(self):
        """
        Identify vertices where the form touches intrados/extrados and add them to 'Cracks' group.

        Parameters
        ----------
        tol : float, optional
            Tolerance for comparing vertex z to lb/ub values.
        """

        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["cracks"]

        for key in formdiagram.vertices():  # type: ignore
            x, y, z = formdiagram.vertex_coordinates(key)  # type: ignore
            lb = formdiagram.vertex_attribute(key, "lb")  # type: ignore
            ub = formdiagram.vertex_attribute(key, "ub")  # type: ignore
            if lb is not None:
                grp.add(
                    Point(x, y, lb),
                    name=f"intrados_limit_{key}",  # type: ignore
                    pointsize=self.crack_size,  # type: ignore
                    pointcolor=self.intrados_color,  # type: ignore
                    opacity=0.95,
                )  # type: ignore
            if ub is not None:
                grp.add(
                    Point(x, y, ub),
                    name=f"extrados_limit_{key}",  # type: ignore
                    pointsize=self.crack_size,  # type: ignore
                    pointcolor=self.extrados_color,  # type: ignore
                    opacity=0.95,
                )  # type: ignore
        self.groups["cracks"] = grp

    def add_forcediagram(self, forcediagram):
        if self.envelope is None:
            return
        self.scene.add(forcediagram, show_faces=False, show_lines=True)

    def add_envelope(self):
        if self.envelope is None:
            return
        envelope = self.envelope

        if envelope.intrados is not None:
            parent: Group = self.groups["intrados"]
            parent.add(
                envelope.intrados,  # type: ignore
                facecolor=self.surfacecolor,  # type: ignore
                edgecolor=self.surfacecolor.darkened(30),
                linewidth=self.surface_linewidth,
                opacity=0.8,  # type: ignore
            )

        if envelope.extrados is not None:
            parent: Group = self.groups["extrados"]
            parent.add(
                envelope.extrados,  # type: ignore
                facecolor=self.surfacecolor,  # type: ignore
                edgecolor=self.surfacecolor.darkened(30),
                linewidth=self.surface_linewidth,
                opacity=0.8,  # type: ignore
            )

        if envelope.middle is not None:
            parent: Group = self.groups["middle"]
            parent.add(
                envelope.middle,  # type: ignore
                facecolor=self.surfacecolor,  # type: ignore
                edgecolor=self.surfacecolor.darkened(30),
                linewidth=self.surface_linewidth,
                opacity=0.8,  # type: ignore
            )
            parent.show = False

        if envelope.fill is not None:
            parent: Group = self.groups["fill"]
            parent.add(
                envelope.fill,  # type: ignore
                facecolor=self.surfacecolor,  # type: ignore
                edgecolor=self.surfacecolor.darkened(30),
                linewidth=self.surface_linewidth,
                opacity=0.8,  # type: ignore
            )
            parent.show = False

    def add_selfweight_arrows(self):
        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["selfweight"]

        # Calculate the diagonal distance of the form diagram for scaling
        vertices_xy = [formdiagram.vertex_coordinates(vertex)[:2] for vertex in formdiagram.vertices()]
        bbox = bounding_box_xy(vertices_xy)
        diagonal_distance = math.sqrt((bbox[1][0] - bbox[0][0]) ** 2 + (bbox[1][1] - bbox[0][1]) ** 2)

        # Get all force magnitudes to find the maximum for scaling
        force_magnitudes = []
        for vertex in formdiagram.vertices():
            px = formdiagram.vertex_attribute(vertex, "px") or 0.0
            py = formdiagram.vertex_attribute(vertex, "py") or 0.0
            pz = formdiagram.vertex_attribute(vertex, "pz") or 0.0
            magnitude = math.sqrt(px**2 + py**2 + pz**2)
            force_magnitudes.append(magnitude)

        max_magnitude = max(force_magnitudes) if force_magnitudes else 1.0

        # Calculate scale so that the longest force vector is 1/16 of the diagonal distance
        if max_magnitude > 0:
            target_length = diagonal_distance / 16.0
            force_scale = target_length / max_magnitude
        else:
            force_scale = 1.0

        for key in formdiagram.vertices():
            x, y, z = formdiagram.vertex_coordinates(key)
            px = formdiagram.vertex_attribute(key, "px") or 0.0
            py = formdiagram.vertex_attribute(key, "py") or 0.0
            pz = formdiagram.vertex_attribute(key, "pz") or 0.0

            # Calculate force magnitude
            force_magnitude = math.sqrt(px**2 + py**2 + pz**2)

            # Only draw if force is significant
            if force_magnitude > 1e-6:
                # Create force vector pointing to the vertex
                force_vector = Vector(px * force_scale, py * force_scale, pz * force_scale)

                # Set anchor point at the start of the arrow (X - P)
                anchor_point = Point(x - px * force_scale, y - py * force_scale, z - pz * force_scale)

                # Add the arrow to the group
                grp.add(force_vector, anchor=anchor_point, name=f"Selfweight_{key}_F={force_magnitude:.1f}", linecolor=self.form_color, linewidth=2.0, opacity=0.8)

    def add_evelope_limits(self):
        if self.formdiagram is None:
            return
        else:
            formdiagram = self.formdiagram  # type: ignore

        grp: Group = self.groups["envelope_limits"]

        for key in formdiagram.vertices():
            x, y, z = formdiagram.vertex_coordinates(key)
            lb = formdiagram.vertex_attribute(key, "lb")
            ub = formdiagram.vertex_attribute(key, "ub")
            if lb is not None:
                grp.add(Point(x, y, lb), name=f"lb_{key}", pointsize=self.crack_size / 2, pointcolor=self.intrados_color, opacity=0.95)  # type: ignore
            if ub is not None:
                grp.add(Point(x, y, ub), name=f"ub_{key}", pointsize=self.crack_size / 2, pointcolor=self.extrados_color, opacity=0.95)  # type: ignore
            if lb is not None and ub is not None:
                grp.add(Line(Point(x, y, lb), Point(x, y, ub)), name=f"line_{key}", linecolor=Color.black(), linewidth=1.0, opacity=0.95)  # type: ignore

    # =============================================================================
    # Graph
    # =============================================================================

    def add_graph(self):
        if self.blockmodel is None:
            return
        parent: Group = self.groups["interactions"]

        node_point = {node: self.blockmodel.graph.node_element(node).point for node in self.blockmodel.graph.nodes()}  # type: ignore
        points = list(node_point.values())
        lines = [Line(node_point[u], node_point[v]) for u, v in self.blockmodel.graph.edges()]

        nodegroup = self.scene.add_group(name="Nodes", parent=parent)  # type: ignore
        edgegroup = self.scene.add_group(name="Edges", parent=parent)  # type: ignore

        nodegroup.add_from_list(points, pointsize=10, pointcolor=self.graphnodecolor)  # type: ignore
        edgegroup.add_from_list(lines, linewidth=1, linecolor=self.graphedgecolor)  # type: ignore
