from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_session.lazyload import LazyLoadSession

from .settings import MasonrySettings


class MasonrySession(LazyLoadSession):
    settingsclass = MasonrySettings
    settings: MasonrySettings  # type: ignore

    # set a fail message

    # =============================================================================
    # BlockModel state
    # =============================================================================

    MODEL_LAYERS = [
        "Masonry::Model::Blocks",
        "Masonry::Model::Supports",
        "Masonry::Model::Interactions",
        "Masonry::Model::Contacts",
    ]

    def clear_model(self) -> None:
        """Remove the current BlockModel and everything that depends on it.

        Removes the model's scene objects, clears the model layers, and
        deletes the dependent session artefacts (problem, results), which are
        invalid once the model changes.
        """
        # Rhino/compas_dem imports are local so this module stays importable
        # outside Rhino (headless tests) and cheap to import for TNA commands.
        import compas_rhino.layers
        from compas_dem.elements import Block
        from compas_dem.interactions import FrictionContact
        from compas_model.models import InteractionGraph

        for key in ("blockmodel", "problem", "results"):
            self.delete(key)

        for itemtype in (Block, FrictionContact, InteractionGraph):
            for obj in self.scene.find_all_by_itemtype(itemtype):
                self.scene.remove(obj)

        for layer in self.MODEL_LAYERS:
            compas_rhino.layers.clear_layer(layer)

    def set_model(self, model) -> None:
        """Install `model` as the session BlockModel and draw it.

        Clears the previous model (and dependent problem/results) first.
        This is the shared tail of every model-creating command
        (Model_blocks, Model_import, TNA_blockexports, ...).

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`

        """
        self.clear_model()
        self["blockmodel"] = model
        self.draw_model()

    def draw_model(self) -> None:
        """Draw the session BlockModel: blocks, and (if contacts have been
        computed) the interaction graph and contact interfaces."""
        model = self.get("blockmodel")
        if model is None:
            return

        for block in model.elements():
            node = block.graphnode
            layer = "Masonry::Model::Supports" if block.is_support else "Masonry::Model::Blocks"
            self.scene.add(
                block,  # type: ignore
                name=f"Block_{node}",  # type: ignore
                group=f"Masonry::Model::Blocks::{node}",  # type: ignore
                layer=layer,  # type: ignore
            )

        if model.graph.number_of_edges() > 0:
            self.scene.add(model.graph, layer="Masonry::Model::Interactions")  # type: ignore
            for contact in model.contacts():
                self.scene.add(contact, layer="Masonry::Model::Contacts")  # type: ignore

        self.redraw()

    def redraw(self) -> None:
        """Redraw the scene and re-tag Block guids and materials.

        Scene.redraw() recreates every drawn Rhino object, not just newly
        added ones, so guids change on every redraw. Route all redraws
        through here so the "element_guid"/"material_guid" tags never go stale.
        """
        self.scene.redraw()
        model = self.get("blockmodel")
        if model is not None:
            self._tag_block_guids(model)
            self._tag_block_materials(model)
            self._tag_block_supports(model)

    def sync_support_layers(self) -> None:
        """Route each block scene object to the Supports/Blocks layer per is_support.

        Call before redraw() after changing is_support flags. Layer and colour
        both derive from is_support (the scene object colours supports red), so
        there's no manual per-object ObjectLayer to fight the redraw or hold
        stale guids.
        """
        from compas_dem.elements import Block

        for sceneobj in self.scene.find_all_by_itemtype(Block):
            sceneobj.layer = "Masonry::Model::Supports" if sceneobj.item.is_support else "Masonry::Model::Blocks"

    def _tag_block_guids(self, model) -> None:
        import rhinoscriptsyntax as rs  # type: ignore

        for sceneobj in self.scene.find_all_by_itemtype(Block):
            for guid in sceneobj.guids:
                rs.SetUserText(guid, "element_guid", str(sceneobj.item.guid))

    def _tag_block_materials(self, model) -> None:
        """Tag each Block's Rhino object with its material's persistent guid.

        Blocks without an assigned material have the tag removed (passing
        `None` to SetUserText deletes the key) so a stale tag can't survive
        a material being unassigned.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        for sceneobj in self.scene.find_all_by_itemtype(Block):
            material = sceneobj.item.material
            value = str(material.guid) if material is not None else None
            for guid in sceneobj.guids:
                rs.SetUserText(guid, "material_guid", value)

    def _tag_block_supports(self, model) -> None:
        """Tag each Block's Rhino object with its is_support flag (User Text).

        Written via the generic set_user_params so it JSON-encodes to
        true/false — a machine-readable support marker alongside the red
        colour and Supports layer. Re-applied here so it survives redraws.
        """
        for sceneobj in self.scene.find_all_by_itemtype(Block):
            for guid in sceneobj.guids:
                self.set_user_params(guid, {"is_support": bool(sceneobj.item.is_support)})

    def guid_element_map(self, model=None) -> dict:
        """Map each Block element's persistent guid (str) to its current graph node.
        Rebuild per-command, not cached — node indices shift as the model changes.

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`, optional
            The model to use. If not provided, the session's current BlockModel is used.

        Returns
        -------
        dict
            A dictionary mapping Rhino GUIDs to Block elements.
        """
        model: BlockModel

        model = model or self.get("blockmodel")
        return {str(model.graph.node_element(n).guid): n for n in model.graph.nodes()}

    def find_node(self, guid, guid_element_map=None):
        """Resolve a Rhino object guid to its current graph node.

        Pass a prebuilt `guid_element_map` when resolving many guids in a loop,
        to avoid rebuilding it per call.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        text = rs.GetUserText(guid, "element_guid")
        if text is None:
            return None
        mapping = guid_element_map if guid_element_map is not None else self.guid_element_map()
        return mapping.get(text)

    def guid_material_map(self, model=None) -> dict:
        """Map each Material's persistent guid (str) to the Material instance.

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`, optional
            The model to use. If not provided, the session's current BlockModel is used.

        Returns
        -------
        dict
            A dictionary mapping Material guids to Material instances.
        """
        model = model or self.get("blockmodel")
        return {str(material.guid): material for material in model.materials()}

    def find_material(self, guid, guid_material_map=None):
        """Resolve a Rhino object guid to its assigned Material, via the "material_guid" tag.

        Pass a prebuilt `guid_material_map` when resolving many guids in a loop,
        to avoid rebuilding it per call. Returns `None` if the object has no
        material tag (no material assigned yet).
        """
        import rhinoscriptsyntax as rs  # type: ignore

        text = rs.GetUserText(guid, "material_guid")
        if text is None:
            return None
        mapping = guid_material_map if guid_material_map is not None else self.guid_material_map()
        return mapping.get(text)

    # =============================================================================
    # Problem state
    # =============================================================================
    #
    # A model can carry MANY problems (same loads, different solver -> new
    # problem). They live in the `problems` dict keyed by name ("Problem_1",
    # ...), with one `active_problem` at a time. Each problem owns a Rhino layer
    # subtree under "Masonry::<name>::...". The Problem object is the source of
    # truth; the Rhino geometry under those layers is *derived* — draw_problem()
    # clears and regenerates it from the Problem's boundary conditions, so
    # add/remove/modify only need to mutate the Problem and redraw.

    # Sublayers created under "Masonry::<problem name>" for every problem.
    PROBLEM_SUBLAYERS = [
        "Loads::Gravity",
        "Loads::Point",
        "Loads::Surface",
        "Boundary conditions::Displacements",
        "Boundary conditions::Rotations",
    ]

    # Display scales now live in settings.blockmodel (scale_loads /
    # scale_gravity / scale_displacement) so they're tunable in Session_settings.
    @property
    def _scales(self):
        bm = self.settings.blockmodel
        return bm.scale_gravity, bm.scale_loads, bm.scale_displacement

    @property
    def problems(self) -> dict:
        """The dict of Problems attached to the current model, keyed by name."""
        return self.setdefault("problems", dict)

    def save_problems(self) -> None:
        """Re-set the problems dict so autosync dumps the mutated Problems to disk."""
        self["problems"] = self.problems

    @property
    def active_problem_name(self):
        return self.get("active_problem")

    def set_active_problem(self, name) -> None:
        self["active_problem"] = name

    def active_problem(self):
        """Return the active Problem instance, or None."""
        name = self.active_problem_name
        return self.problems.get(name) if name is not None else None

    def next_problem_name(self) -> str:
        """Return the next free "Problem_<n>" name."""
        i = 1
        while f"Problem_{i}" in self.problems:
            i += 1
        return f"Problem_{i}"

    def choose_problem(self, message="Problem"):
        """Print the problems with an index and prompt the user to pick one.

        Returns the chosen problem name, or None if there are none / cancelled.
        rs.GetString option keywords can't contain the "Problem_" underscore
        reliably across locales, so selection is by printed index.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        names = list(self.problems.keys())
        if not names:
            return None
        if len(names) == 1:
            return names[0]
        for i, n in enumerate(names):
            print(f"{i}: {n}" + ("  (active)" if n == self.active_problem_name else ""))
        idx = rs.GetString(message=f"{message} index", strings=[str(i) for i in range(len(names))])
        if not idx:
            return None
        return names[int(idx)]

    def problem_layer(self, name, sub=None) -> str:
        """Build a layer path for a problem, optionally with a sublayer suffix."""
        return f"Masonry::{name}::{sub}" if sub else f"Masonry::{name}"

    def ensure_problem_layers(self, name) -> None:
        """Create the full layer subtree for a problem (idempotent)."""
        from compas_rhino.layers import create_layers_from_path

        for sub in self.PROBLEM_SUBLAYERS:
            create_layers_from_path(self.problem_layer(name, sub), separator="::")

    def create_problem(self, model, name=None, source=None):
        """Create (or duplicate) a Problem for `model`, store it, make it active.

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`
        name : str, optional
            Problem name. Defaults to the next free "Problem_<n>".
        source : :class:`compas_dem.problem.Problem`, optional
            If given, deep-copy its boundary conditions, contact properties and
            solver into the new problem (a "duplicate"). Otherwise start fresh
            and inherit supports from the model's `is_support` flags.

        Returns
        -------
        :class:`compas_dem.problem.Problem`
        """
        from compas_dem.problem import Problem

        name = name or self.next_problem_name()
        problem = Problem(model, name=name)

        if source is not None:
            # Data.copy() round-trips through JSON -> deep copy with a fresh guid.
            problem._boundary_conditions = source.boundary_conditions.copy()
            problem._contact_properties = source.contact_properties.copy()
            problem._solver = source._solver.copy() if source._solver else None
        else:
            problem.add_supports_from_model(model)

        self.problems[name] = problem
        self.save_problems()
        self.set_active_problem(name)
        self.ensure_problem_layers(name)
        self.draw_problem(name, model)
        return problem

    def delete_problem(self, name) -> None:
        """Remove a problem and its Rhino layer subtree."""
        from compas_rhino.layers import delete_layers

        self.problems.pop(name, None)
        self.save_problems()
        if self.active_problem_name == name:
            self.set_active_problem(next(iter(self.problems), None))
        delete_layers([self.problem_layer(name)])

    # =============================================================================
    # Generic Rhino User Text <-> params (User Text is a str->str dict per object)
    # =============================================================================

    def set_user_params(self, guid, params: dict) -> None:
        """Write a dict of parameters onto a Rhino object's User Text.

        User Text only stores strings, so non-string values are JSON-encoded and
        strings are stored raw (keeps identifier tags like "element_guid"
        readable and back-compatible with find_node/find_material). A ``None``
        value deletes that key.
        """
        import json

        import rhinoscriptsyntax as rs  # type: ignore

        for key, value in params.items():
            if value is None:
                rs.SetUserText(guid, key, None)
            elif isinstance(value, str):
                rs.SetUserText(guid, key, value)
            else:
                rs.SetUserText(guid, key, json.dumps(value))

    def get_user_params(self, guid, keys=None) -> dict:
        """Read a Rhino object's User Text back into a dict.

        Values are JSON-decoded when possible, else returned as the raw string.
        Pass ``keys`` to read a subset; otherwise every User Text key is read.
        """
        import json

        import rhinoscriptsyntax as rs  # type: ignore

        if keys is None:
            keys = rs.GetUserText(guid) or []
        out = {}
        for key in keys:
            raw = rs.GetUserText(guid, key)
            if raw is None:
                continue
            try:
                out[key] = json.loads(raw)
            except (ValueError, TypeError):
                out[key] = raw
        return out

    # =============================================================================
    # Problem drawing (derived geometry — Problem is the source of truth)
    # =============================================================================

    def draw_problem(self, name, model=None) -> None:
        """Clear and redraw all load / boundary-condition geometry for a problem.

        Every drawn object carries its parameters as Rhino User Text via
        set_user_params: always "problem" and "load_kind", plus the load's own
        values (force / g / load / translation / rotation / transformation) and,
        for block-bound entries, "element_guid" and "bc_index". Display scales
        come from settings.blockmodel (Session_settings).
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas.geometry import Rotation
        from compas.geometry import Translation
        from compas.geometry import Vector
        from compas_rhino.layers import clear_layer

        model = model or self.get("blockmodel")
        problem = self.problems.get(name)
        if model is None or problem is None:
            return

        gravity_scale, load_scale, disp_scale = self._scales

        # Self-healing: recreate the layer subtree if the user deleted it, so
        # activating/redrawing a problem always restores its layers. Idempotent
        # (create_layers_from_path only creates what's missing).
        self.ensure_problem_layers(name)

        for sub in self.PROBLEM_SUBLAYERS:
            clear_layer(self.problem_layer(name, sub))

        bc = problem.boundary_conditions
        blocks = {block.graphnode: block for block in model.elements()}

        # --- gravity: single downward arrow at the world origin ---------------
        if bc.g:
            self._draw_vector(
                name,
                "Loads::Gravity",
                "gravity",
                origin=[0.0, 0.0, 0.0],
                vector=[0.0, 0.0, -bc.g * gravity_scale],
                params={"g": bc.g},
            )

        # --- global body forces: arrows at the origin (accel direction) -------
        for i, acc in enumerate(bc.body_forces):
            self._draw_vector(
                name,
                "Loads::Gravity",
                "body_force",
                origin=[0.0, 0.0, 0.0],
                vector=[c * gravity_scale for c in acc],
                bc_index=i,
                params={"acceleration": acc},
            )

        # --- point loads: arrow from the block centroid along the force -------
        for i, entry in enumerate(bc.point_loads):
            block = blocks.get(entry["block_index"])
            if block is None:
                continue
            origin = entry["point"] if entry["point"] is not None else list(block.point)
            vector = [c * load_scale for c in entry["force"]]
            self._draw_vector(
                name,
                "Loads::Point",
                "point_load",
                origin=origin,
                vector=vector,
                element_guid=str(block.guid),
                bc_index=i,
                params={"force": entry["force"], "point": origin, "moment": entry.get("moment")},
            )

        # --- surface loads: a copy of the loaded face + a pressure arrow ------
        for i, entry in enumerate(bc.surface_loads):
            block = blocks.get(entry["block_index"])
            if block is None:
                continue
            face_index = entry["face_index"]
            params = {"load": entry["load"], "face_index": face_index}
            self._draw_face(
                name,
                "Loads::Surface",
                "surface_load",
                block=block,
                face_index=face_index,
                element_guid=str(block.guid),
                bc_index=i,
                params=params,
            )
            polygon = block.modelgeometry.face_polygon(face_index)
            self._draw_vector(
                name,
                "Loads::Surface",
                "surface_load",
                origin=list(polygon.centroid),
                vector=[c * load_scale for c in entry["load"]],
                element_guid=str(block.guid),
                bc_index=i,
                params=params,
            )

        # --- displacement / rotation BCs: a transformed copy of the block -----
        for i, entry in enumerate(bc.displacements):
            t = entry.get("translation")
            r = entry.get("rotation")
            is_support = t == [0.0, 0.0, 0.0] and r == [0.0, 0.0, 0.0]
            if is_support:
                # Supports are drawn by the model on Masonry::Model::Supports.
                continue
            block = blocks.get(entry["block_index"])
            if block is None:
                continue
            if t is not None:
                vec = [(c or 0.0) * disp_scale for c in t]
                self._draw_transformed_block(
                    name,
                    "Boundary conditions::Displacements",
                    "displacement",
                    block=block,
                    T=Translation.from_vector(vec),
                    element_guid=str(block.guid),
                    bc_index=i,
                    params={"translation": t, "applied_translation": vec},
                )
            if r is not None:
                angle = Vector(*r).length
                if angle:
                    axis = [c / angle for c in r]
                    R = Rotation.from_axis_and_angle(axis, angle * disp_scale, point=list(block.point))
                    self._draw_transformed_block(
                        name,
                        "Boundary conditions::Rotations",
                        "rotation",
                        block=block,
                        T=R,
                        element_guid=str(block.guid),
                        bc_index=i,
                        params={"rotation": r, "applied_angle_rad": angle * disp_scale},
                    )

        rs.Redraw()

    def _load_params(self, name, kind, element_guid=None, bc_index=None, extra=None) -> dict:
        """Assemble the User Text param dict shared by every drawn load/BC object."""
        params = {"problem": name, "load_kind": kind}
        if element_guid is not None:
            params["element_guid"] = element_guid
        if bc_index is not None:
            params["bc_index"] = bc_index
        if extra:
            params.update(extra)
        return params

    def _draw_vector(self, name, sub, kind, origin, vector, element_guid=None, bc_index=None, params=None):
        """Draw an arrow (line with an end arrowhead), tag it, and layer it."""
        import rhinoscriptsyntax as rs  # type: ignore

        end = [o + v for o, v in zip(origin, vector)]
        if end == list(origin):
            return None
        guid = rs.AddLine(origin, end)
        rs.CurveArrows(guid, 2)  # arrowhead at the end
        rs.ObjectLayer(guid, self.problem_layer(name, sub))
        self.set_user_params(guid, self._load_params(name, kind, element_guid, bc_index, params))
        return guid

    def _draw_face(self, name, sub, kind, block, face_index, element_guid=None, bc_index=None, params=None):
        """Draw a copy of a block face as a mesh, tag it, and layer it."""
        import rhinoscriptsyntax as rs  # type: ignore

        polygon = block.modelgeometry.face_polygon(face_index)
        vertices = [list(pt) for pt in polygon.points]
        face = list(range(len(vertices)))
        guid = rs.AddMesh(vertices, [face])
        if guid is None:
            return None
        rs.ObjectLayer(guid, self.problem_layer(name, sub))
        self.set_user_params(guid, self._load_params(name, kind, element_guid, bc_index, params))
        return guid

    def _draw_transformed_block(self, name, sub, kind, block, T, element_guid=None, bc_index=None, params=None):
        """Draw a copy of the block mesh with the BC transformation applied.

        The transformation matrix is stored in User Text alongside the raw BC
        values, so the prescribed displacement/rotation is both visible (the
        block moves) and machine-readable.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        mesh = block.modelgeometry.transformed(T)
        vertices, faces = mesh.to_vertices_and_faces()
        guid = rs.AddMesh(vertices, faces)
        if guid is None:
            return None
        rs.ObjectLayer(guid, self.problem_layer(name, sub))
        extra = dict(params or {})
        extra["transformation"] = [list(row) for row in T.matrix]
        self.set_user_params(guid, self._load_params(name, kind, element_guid, bc_index, extra))
        return guid
