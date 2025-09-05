import compas_rhino.conversions
import rhinoscriptsyntax as rs  # type: ignore
import scriptcontext as sc  # type: ignore

from compas.colors import Color
from compas.geometry import Cylinder
from compas.geometry import Line
from compas.geometry import Vector
from compas.scene.descriptors.color import ColorAttribute
from compas.scene.descriptors.colordict import ColorDictAttribute
from compas_rui.scene import RUIMeshObject
from compas_session.lazyload import LazyLoadSession as Session
from compas_tna.diagrams import FormDiagram


class RhinoFormDiagramObject(RUIMeshObject):
    session = Session()

    vertexcolor = ColorDictAttribute(default=Color.purple())
    edgecolor = ColorDictAttribute(default=Color.purple().darkened(50))
    facecolor = ColorDictAttribute(default=Color.purple().lightened(25))

    freecolor = ColorAttribute(default=Color.white())
    supportcolor = ColorAttribute(default=Color.red())
    fixedcolor = ColorAttribute(default=Color.cyan())

    residualcolor = ColorAttribute(default=Color.cyan())
    reactioncolor = ColorAttribute(default=Color.green())

    loadcolor = ColorAttribute(default=Color.green().darkened(50))
    selfweightcolor = ColorAttribute(default=Color.white())

    compressioncolor = ColorAttribute(default=Color.blue())
    tensioncolor = ColorAttribute(default=Color.red())

    def __init__(
        self,
        show_supports=True,
        show_fixed=True,
        show_free=False,
        vertexgroup="RhinoVAULT::FormDiagram::Vertices",
        edgegroup="RhinoVAULT::FormDiagram::Edges",
        facegroup="RhinoVAULT::FormDiagram::Faces",
        loadgroup="RhinoVAULT::FormDiagram::Loads",
        selfweightgroup="RhinoVAULT::FormDiagram::Selfweight",
        forcegroup="RhinoVAULT::FormDiagram::Forces",
        reactiongroup="RhinoVAULT::FormDiagram::Reactions",
        residualgroup="RhinoVAULT::FormDiagram::Residuals",
        layer="RhinoVAULT::FormDiagram",
        disjoint=True,
        **kwargs,
    ):
        super().__init__(
            disjoint=disjoint,
            vertexgroup=vertexgroup,
            edgegroup=edgegroup,
            facegroup=facegroup,
            layer=layer,
            **kwargs,
        )

        self.show_faces = True
        self.show_edges = False
        self.show_supports = show_supports
        self.show_fixed = show_fixed
        self.show_free = show_free
        self.loadgroup = loadgroup
        self.selfweightgroup = selfweightgroup
        self.forcegroup = forcegroup
        self.reactiongroup = reactiongroup
        self.residualgroup = residualgroup

    # =============================================================================
    # Properties
    # =============================================================================

    @property
    def settings(self):
        settings = super().settings
        settings["show_supports"] = self.show_supports
        settings["show_fixed"] = self.show_fixed
        settings["show_free"] = self.show_free
        return settings

    @property
    def diagram(self) -> FormDiagram:
        return self.mesh  # type: ignore

    @diagram.setter
    def diagram(self, diagram: FormDiagram) -> None:
        self.mesh = diagram

    # =============================================================================
    # Helpers
    # =============================================================================

    def supports(self) -> list[int]:
        return list(self.diagram.vertices_where(is_support=True))  # type: ignore

    def vertex_is_support(self, vertex) -> bool:
        return bool(self.diagram.vertex_attribute(vertex, "is_support"))

    def vertex_is_fixed(self, vertex) -> bool:
        return bool(self.diagram.vertex_attribute(vertex, "is_fixed"))

    def vertex_residual(self, vertex) -> Vector:
        return Vector(*self.diagram.vertex_attributes(vertex, ["_rx", "_ry", "_rz"]))  # type: ignore

    def vertex_weight(self, vertex) -> float:
        weight = 0
        thickness = self.diagram.vertex_attribute(vertex, "t")
        if thickness:
            area = self.diagram.vertex_area(vertex)
            weight = area * thickness
        return weight

    def vertex_load(self, vertex) -> Vector:
        return Vector(*self.diagram.vertex_attributes(vertex, ["px", "py", "pz"]))  # type: ignore

    def vertex_load_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.load"

    def vertex_selfweight_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.selfweight"

    def edges(self, **kwargs) -> list[tuple[int, int]]:
        return list(self.diagram.edges_where(_is_edge=True))  # type: ignore

    def faces(self, **kwargs) -> list[int]:
        return list(self.diagram.faces_where(_is_loaded=True))  # type: ignore

    def forces(self) -> list[float]:
        return self.diagram.edges_attribute("_f", keys=self.edges())  # type: ignore

    def edge_force(self, edge) -> float:
        return self.diagram.edge_attribute(edge, "_f") or 0.0

    def compute_vertex_color(self, vertex) -> Color:
        if self.vertex_is_support(vertex):
            color = self.supportcolor
        elif self.vertex_is_fixed(vertex):
            color = self.fixedcolor
        else:
            color = self.freecolor
        return color  # type: ignore

    def compute_visible_vertices(self) -> list[int]:
        vertices = []
        if self.show_free:
            vertices += list(self.diagram.vertices_where(is_support=False, is_fixed=False))
        if self.show_fixed:
            vertices += list(self.diagram.vertices_where(is_fixed=True))
        if self.show_supports:
            vertices += list(self.diagram.vertices_where(is_support=True))
        return vertices

    def compute_edge_colors(self, tol=1e-3) -> list[Color]:
        forces = self.forces()
        magnitudes = [abs(f) for f in forces]
        fmin = min(magnitudes)
        fmax = max(magnitudes)

        colors = []

        if fmax - fmin >= tol:
            # size of the range of forces is already checked here
            # no need to check again in the loop
            for magnitude in magnitudes:
                # this will need to be updated once we allow for tension forces
                # or we have to exclude tension forces from the calculation
                # and give tension edges their own style
                colors.append(Color.from_i((magnitude - fmin) / (fmax - fmin)))

        return colors

    def compute_pipe_colors(self, tol=1e-3) -> dict[tuple[int, int], Color]:
        edges = self.edges()
        forces = [self.edge_force(edge) for edge in edges]
        magnitudes = [abs(f) for f in forces]
        fmin = min(magnitudes)
        fmax = max(magnitudes)

        edge_color = {}

        if fmax - fmin >= tol:
            for edge, force, magnitude in zip(edges, forces, magnitudes):
                # this will need to be updated when we include tension edges
                edge_color[edge] = Color.from_i((magnitude - fmin) / (fmax - fmin))

        return edge_color

    # =============================================================================
    # Clear
    # =============================================================================

    # =============================================================================
    # Draw
    # =============================================================================

    def draw(self):
        faces = []
        if self.show_faces:
            faces += list(self.faces())
        if faces:
            self.show_faces = faces

        for vertex in self.diagram.vertices():
            self.vertexcolor[vertex] = self.compute_vertex_color(vertex)

        super().draw()

        return self.guids

    def draw_vertices(self):
        if self.show_vertices is True:
            self.show_vertices = self.compute_visible_vertices()

        for vertex in self.diagram.vertices():
            self.vertexcolor[vertex] = self.compute_vertex_color(vertex)

        return super().draw_vertices()

    def draw_edges(self):
        if self.show_edges is True:
            self.show_edges = list(self.edges())

        return super().draw_edges()

    def draw_faces(self):
        if self.show_faces:
            self.show_faces = list(self.faces())

        return super().draw_faces()

    # =============================================================================
    # Redraw
    # =============================================================================

    def redraw_vertices(self):
        rs.EnableRedraw(False)
        self.clear_vertices()
        self.draw_vertices()
        rs.EnableRedraw(True)
        rs.Redraw()

    def redraw_edges(self):
        rs.EnableRedraw(False)
        self.clear_edges()
        self.draw_edges()
        rs.EnableRedraw(True)
        rs.Redraw()

    def redraw_faces(self):
        rs.EnableRedraw(False)
        self.clear_faces()
        self.draw_faces()
        rs.EnableRedraw(True)
        rs.Redraw()

    def redraw(self):
        rs.EnableRedraw(False)
        self.clear()
        self.draw()
        rs.EnableRedraw(True)
        rs.Redraw()

    # =============================================================================
    # Structural
    # =============================================================================

    def draw_loads(self):
        guids = []

        color = self.loadcolor
        scale = 1.0
        tol = 1e-3
        # scale = self.session.settings.drawing.scale_loads
        # tol = self.session.settings.drawing.tol_vectors

        for vertex in self.diagram.vertices_where(is_support=False):
            load = self.vertex_load(vertex)

            if load is not None:
                vector = load * scale
                if vector.length > tol:
                    name = self.vertex_load_name(vertex)
                    attr = self.compile_attributes(name=name, color=color, arrow="start")
                    point = self.diagram.vertex_point(vertex)
                    line = Line.from_point_and_vector(point, vector)
                    guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(line), attr)
                    guids.append(guid)

        if guids:
            if self.loadgroup:
                self.add_to_group(self.loadgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_selfweight(self):
        guids = []

        color = self.selfweightcolor
        scale = 1.0
        tol = 1e-3
        # scale = self.session.settings.drawing.scale_selfweight
        # tol = self.session.settings.drawing.tol_vectors

        for vertex in self.diagram.vertices_where(is_support=False):
            weight = self.vertex_weight(vertex)
            if weight:
                point = self.diagram.vertex_point(vertex)
                vector = Vector(0, 0, -weight * scale)
                if vector.length > tol:
                    line = Line.from_point_and_vector(point, vector)
                    name = self.vertex_selfweight_name(vertex)
                    attr = self.compile_attributes(name=name, color=color, arrow="end")
                    guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(line), attr)
                    guids.append(guid)

        if guids:
            if self.selfweightgroup:
                self.add_to_group(self.selfweightgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_pipes(self):
        guids = []

        scale = 1.0
        tol = 1e-3
        # scale = self.session.settings.drawing.scale_pipes
        # tol = self.session.settings.drawing.tol_pipes

        pipe_colors = self.compute_pipe_colors()

        for edge in self.edges():
            force = self.edge_force(edge)

            if force:
                line = self.diagram.edge_line(edge)
                radius = abs(force) * scale

                color = self.compressioncolor
                if self.session.settings.drawing.show_forces:
                    color = pipe_colors[edge]

                if radius > tol:
                    pipe = Cylinder.from_line_and_radius(line, radius)
                    name = "{}.edge.{}.force".format(self.diagram.name, edge)
                    attr = self.compile_attributes(name=name, color=color)
                    guid = sc.doc.Objects.AddBrep(compas_rhino.conversions.cylinder_to_rhino_brep(pipe), attr)
                    guids.append(guid)

        if guids:
            if self.forcegroup:
                self.add_to_group(self.forcegroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_reactions(self):
        guids = []

        scale = self.session.settings.drawing.scale_reactions
        tol = self.session.settings.drawing.tol_vectors

        for vertex in self.supports():
            residual = self.vertex_residual(vertex)
            vector = residual * scale

            if vector.length > tol:
                name = "{}.vertex.{}.reaction".format(self.diagram.name, vertex)
                attr = self.compile_attributes(name=name, color=self.reactioncolor, arrow="start")
                point = self.diagram.vertex_point(vertex)
                line = Line.from_point_and_vector(point, vector)
                guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(line), attr)
                guids.append(guid)

        if guids:
            if self.reactiongroup:
                self.add_to_group(self.reactiongroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_residuals(self):
        guids = []

        scale = self.session.settings.drawing.scale_residuals
        tol = self.session.settings.drawing.tol_vectors

        for vertex in self.diagram.vertices_where(is_support=False):
            residual = self.vertex_residual(vertex)

            vector = residual * scale
            if vector.length > tol:
                name = "{}.vertex.{}.residual".format(self.diagram.name, vertex)
                attr = self.compile_attributes(name=name, color=self.residualcolor, arrow="end")
                point = self.diagram.vertex_point(vertex)
                line = Line.from_point_and_vector(point, vector)
                guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(line), attr)
                guids.append(guid)

        if guids:
            if self.residualgroup:
                self.add_to_group(self.residualgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids
