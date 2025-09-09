from math import sqrt
from typing import Optional

import rhinoscriptsyntax as rs  # type: ignore
import scriptcontext as sc  # type: ignore

import compas_rhino.conversions
from compas.colors import Color
from compas.geometry import Cylinder
from compas.geometry import Line
from compas.geometry import Sphere
from compas.geometry import Vector
from compas.scene.descriptors.color import ColorAttribute
from compas.scene.descriptors.colordict import ColorDictAttribute
from compas_masonry.session import MasonrySession as Session
from compas_rui.scene import RUIMeshObject
from compas_tna.diagrams import FormDiagram


class RhinoFormDiagramObject(RUIMeshObject):
    session: Session = Session()

    vertexcolor = ColorDictAttribute(default=Color.white())
    edgecolor = ColorDictAttribute(default=Color.black())
    facecolor = ColorDictAttribute(default=Color.white())

    freecolor = ColorAttribute(default=Color.white())
    supportcolor = ColorAttribute(default=Color.red())
    fixedcolor = ColorAttribute(default=Color.cyan())

    residualcolor = ColorAttribute(default=Color.cyan())
    reactioncolor = ColorAttribute(default=Color.green())

    loadcolor = ColorAttribute(default=Color.green().darkened(50))
    compressioncolor = ColorAttribute(default=Color.blue())
    tensioncolor = ColorAttribute(default=Color.red())

    ecrackcolor = ColorAttribute(default=Color.green())
    icrackcolor = ColorAttribute(default=Color.blue())

    boundscolor = ColorAttribute(default=Color.magenta())

    def __init__(
        self,
        disjoint=True,
        show_vertices=True,
        show_edges=True,
        show_faces=False,
        vertexgroup="RhinoVAULT::FormDiagram::Vertices",
        edgegroup="RhinoVAULT::FormDiagram::Edges",
        facegroup="RhinoVAULT::FormDiagram::Faces",
        layer="RhinoVAULT::FormDiagram",
        show_supports=True,
        show_fixed=True,
        show_free=False,
        loadgroup="RhinoVAULT::FormDiagram::Loads",
        forcegroup="RhinoVAULT::FormDiagram::Forces",
        reactiongroup="RhinoVAULT::FormDiagram::Reactions",
        residualgroup="RhinoVAULT::FormDiagram::Residuals",
        crackgroup="RhinoVAULT::FormDiagram::Cracks",
        boundsgroup="RhinoVAULT::FormDiagram::Bounds",
        **kwargs,
    ):
        super().__init__(
            disjoint=disjoint,
            show_vertices=show_vertices,
            show_edges=show_edges,
            show_faces=show_faces,
            vertexgroup=vertexgroup,
            edgegroup=edgegroup,
            facegroup=facegroup,
            layer=layer,
            **kwargs,
        )

        self.show_supports = show_supports
        self.show_fixed = show_fixed
        self.show_free = show_free

        self.loadgroup = loadgroup
        self.forcegroup = forcegroup
        self.reactiongroup = reactiongroup
        self.residualgroup = residualgroup
        self.crackgroup = crackgroup
        self.boundsgroup = boundsgroup

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

    def vertices(self, **kwargs) -> list[int]:
        return list(self.diagram.vertices())  # type: ignore

    def edges(self, **kwargs) -> list[tuple[int, int]]:
        return list(self.diagram.edges_where(_is_edge=True))  # type: ignore

    def faces(self, **kwargs) -> list[int]:
        return list(self.diagram.faces_where(_is_loaded=True))  # type: ignore

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

    def vertex_bound(self, vertex) -> Optional[Line]:
        ub = self.diagram.vertex_attribute(vertex, "ub")
        lb = self.diagram.vertex_attribute(vertex, "lb")
        if ub and lb:
            point = self.diagram.vertex_point(vertex)
            a = point.copy()
            a.z = ub
            b = point.copy()
            b.z = lb
            return Line(a, b)

    def vertex_is_on_upper_bound(self, vertex, tol=1e-6) -> bool:
        ub = self.diagram.vertex_attribute(vertex, "ub")
        if ub is None:
            return False
        point = self.diagram.vertex_point(vertex)
        return abs(point.z - ub) < tol

    def vertex_is_on_lower_bound(self, vertex, tol=1e-6) -> bool:
        lb = self.diagram.vertex_attribute(vertex, "lb")
        if lb is None:
            return False
        point = self.diagram.vertex_point(vertex)
        return abs(point.z - lb) < tol

    def forces(self) -> list[float]:
        Q = [self.diagram.edge_attribute(edge, "q") or 0.0 for edge in self.edges()]
        L = [self.diagram.edge_length(edge) or 0.0 for edge in self.edges()]
        return [q * l for q, l in zip(Q, L)]  # noqa: E741

    def edge_force(self, edge) -> float:
        q = self.diagram.edge_attribute(edge, "q") or 0.0
        l = self.diagram.edge_length(edge) or 0.0  # noqa: E741
        return q * l

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
            for magnitude in magnitudes:
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
                edge_color[edge] = Color.from_i((magnitude - fmin) / (fmax - fmin))

        return edge_color

    # =============================================================================
    # Names
    # =============================================================================

    def vertex_load_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.load"

    def vertex_selfweight_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.selfweight"

    def vertex_reaction_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.reaction"

    def vertex_residual_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.residual"

    def vertex_bound_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.bound"

    def vertex_crack_name(self, vertex) -> str:
        return f"{self.diagram.name}.vertex.{vertex}.crack"

    def edge_pipe_name(self, edge) -> str:
        return f"{self.diagram.name}.edge.{edge}.pipe"

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

        for vertex in self.vertices():
            self.vertexcolor[vertex] = self.compute_vertex_color(vertex)

        super().draw()

        if self.session.settings.formdiagram.show_reactions:
            self.draw_reactions()

        if self.session.settings.formdiagram.show_residuals:
            self.draw_residuals()

        if self.session.settings.formdiagram.show_pipes:
            self.draw_pipes()

        if self.session.settings.formdiagram.show_loads:
            self.draw_loads()

        if self.session.settings.formdiagram.show_bounds:
            self.draw_bounds()

        if self.session.settings.formdiagram.show_cracks:
            self.draw_cracks()

        return self.guids

    def draw_vertices(self):
        if self.show_vertices is True:
            self.show_vertices = self.compute_visible_vertices()

        for vertex in self.vertices():
            self.vertexcolor[vertex] = self.compute_vertex_color(vertex)

        return super().draw_vertices()

    def draw_edges(self):
        if self.show_edges is True:
            self.show_edges = self.edges()

        return super().draw_edges()

    def draw_faces(self):
        if self.show_faces:
            self.show_faces = self.faces()

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
        scale = self.session.settings.formdiagram.scale_loads
        tol = self.session.settings.formdiagram.tol_vectors

        for vertex in self.diagram.vertices_where(is_support=False):
            load = self.vertex_load(vertex)
            if load is not None:
                vector = load * scale
                if vector.length > tol:
                    name = self.vertex_load_name(vertex)
                    attr = self.compile_attributes(name=name, color=color, arrow="end")
                    point = self.diagram.vertex_point(vertex)
                    line = Line(point + vector, point)
                    guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(line), attr)
                    guids.append(guid)

        if guids:
            if self.loadgroup:
                self.add_to_group(self.loadgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_pipes(self):
        guids = []
        scale = self.session.settings.formdiagram.scale_pipes
        tol = self.session.settings.formdiagram.tol_pipes

        for edge in self.edges():
            force = self.edge_force(edge)
            if force:
                line = self.diagram.edge_line(edge)
                radius = sqrt(abs(force)) * scale
                color = self.compressioncolor
                if radius > tol:
                    pipe = Cylinder.from_line_and_radius(line, radius)
                    name = self.edge_pipe_name(edge)
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
        scale = self.session.settings.formdiagram.scale_reactions
        tol = self.session.settings.formdiagram.tol_vectors

        for vertex in self.supports():
            residual = self.vertex_residual(vertex)
            vector = residual * -scale
            if vector.length > tol:
                name = self.vertex_reaction_name(vertex)
                attr = self.compile_attributes(name=name, color=self.reactioncolor, arrow="end")
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
        scale = self.session.settings.formdiagram.scale_residuals
        tol = self.session.settings.formdiagram.tol_vectors

        for vertex in self.diagram.vertices_where(is_support=False):
            residual = self.vertex_residual(vertex)
            vector = residual * scale
            if vector.length > tol:
                name = self.vertex_residual_name(vertex)
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

    # =============================================================================
    # Envelope
    # =============================================================================

    def draw_bounds(self):
        guids = []

        for vertex in self.vertices():
            bound = self.vertex_bound(vertex)
            if bound:
                name = self.vertex_bound_name(vertex)
                attr = self.compile_attributes(name=name, color=self.boundscolor)

                guid = sc.doc.Objects.AddLine(compas_rhino.conversions.line_to_rhino(bound), attr)
                guids.append(guid)

                guid = sc.doc.Objects.AddPoint(compas_rhino.conversions.point_to_rhino(bound.start), attr)
                guids.append(guid)

                guid = sc.doc.Objects.AddPoint(compas_rhino.conversions.point_to_rhino(bound.end), attr)
                guids.append(guid)

        if guids:
            if self.boundsgroup:
                self.add_to_group(self.boundsgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids

    def draw_cracks(self):
        guids = []

        for vertex in self.vertices():
            if self.vertex_is_on_lower_bound(vertex):
                name = self.vertex_crack_name(vertex)
                attr = self.compile_attributes(name=name, color=self.icrackcolor)
            elif self.vertex_is_on_upper_bound(vertex):
                name = self.vertex_crack_name(vertex)
                attr = self.compile_attributes(name=name, color=self.ecrackcolor)
            else:
                continue

            point = self.diagram.vertex_point(vertex)
            radius = self.session.settings.formdiagram.crack_radius
            sphere = Sphere(radius, point=point)
            guid = sc.doc.Objects.AddSphere(compas_rhino.conversions.sphere_to_rhino(sphere), attr)
            guids.append(guid)

        if guids:
            if self.crackgroup:
                self.add_to_group(self.crackgroup, guids)
            elif self.group:
                self.add_to_group(self.group, guids)

        self._guids += guids
        return guids
