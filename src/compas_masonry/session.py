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
        from compas_dem.interactions import EdgeContact
        from compas_dem.interactions import FrictionContact
        from compas_dem.interactions import VertexContact
        from compas_model.models import InteractionGraph

        # "problems" is the key the plugin actually writes; deleting "problem"
        # left every Problem in the session pointing at a model that was gone.
        for key in ("blockmodel", "problems", "active_problem", "results", "bc_kinds"):
            self.delete(key)

        # obj.clear() purges the object's own guids, which raises on a guid Rhino
        # can no longer resolve — same trap as a redraw, so prune first.
        self.prune_stale_guids()

        # EdgeContact and VertexContact (degenerate, post-displacement contacts)
        # are plain Data subclasses, NOT subclasses of FrictionContact, and
        # find_all_by_itemtype matches with isinstance — so filtering on
        # FrictionContact alone leaves their scene objects behind.
        for itemtype in (Block, FrictionContact, EdgeContact, VertexContact, InteractionGraph):
            for obj in self.scene.find_all_by_itemtype(itemtype):
                # clear() first: removing a scene object drops its guids from the
                # scene while the Rhino objects live on, untracked
                obj.clear()
                self.scene.remove(obj)

        for layer in self.MODEL_LAYERS:
            compas_rhino.layers.clear_layer(layer)
            compas_rhino.layers.delete_layers([layer])

    # Everything the plugin ever draws lives under this root, so clearing it is
    # what makes "clear the session" actually empty the document.
    ROOT_LAYER = "Masonry"

    # Session keys the plugin owns. `problems` (not "problem") is the real key —
    # getting that wrong leaves stale Problems pointing at a deleted model.
    SESSION_KEYS = [
        "blockmodel",
        "problems",
        "active_problem",
        "results",
        "bc_kinds",
        "envelope",
        "formdiagram",
        "analysis",
    ]

    def clear_all(self) -> None:
        """Empty the session: scene objects, every session key, every layer.

        `clear_model` only handles the model layers, so problems, boundary
        conditions and results used to survive a "clear session" both as
        Rhino geometry and as session state. Clearing the ROOT layer with
        `include_children` sweeps the whole tree, including any orphans left
        behind by an earlier crash, and deleting it removes the layers too.
        """
        import compas_rhino.layers

        # obj.clear() purges guids through the same path as a redraw, so a guid
        # Rhino can no longer resolve would raise here — prune first (§1.6 rule 1).
        self.prune_stale_guids()

        for sceneobject in list(self.scene.objects):
            # clear() before remove(): removing first drops the guids from the
            # scene while the Rhino objects live on, untracked (§1.6 rule 2).
            sceneobject.clear()
            self.scene.remove(sceneobject)

        for key in self.SESSION_KEYS:
            self.delete(key)

        compas_rhino.layers.clear_layer(self.ROOT_LAYER)
        compas_rhino.layers.delete_layers([self.ROOT_LAYER])

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

    def prune_stale_guids(self) -> int:
        """Drop guids of Rhino objects that no longer exist from the scene objects.

        `Scene.redraw()` purges every guid its scene objects still hold, and
        `compas_rhino.objects.purge_objects` dereferences the result of
        `find_object(guid)` without checking it::

            AttributeError: 'NoneType' object has no attribute 'RuntimeSerialNumber'

        So a scene object holding a guid whose Rhino object is gone breaks the
        next redraw of the *whole* scene. That happens whenever something
        deletes drawn geometry behind the scene's back — `clear_layer`, or the
        user deleting an object in the viewport.

        Letting that crash through is expensive, not just noisy: `Scene.clear()`
        nulls every scene object's `_guids` *before* purging them, so a crash
        mid-purge leaves the scene tracking nothing while all the Rhino objects
        remain in the document. Those orphans are invisible to later redraws and
        the next draw stacks a fresh set on top of them — two copies of
        everything.

        A guid is only dropped when the lookup `purge_objects` itself uses says
        the object is gone — otherwise the redraw would stop deleting objects
        it is supposed to delete, and every redraw would leave a duplicate.
        A guid that lookup cannot resolve but the current document still can is
        deleted directly, so it cannot be orphaned either; that has not been
        observed in practice and is cheap insurance rather than a diagnosis.

        Returns
        -------
        int
            The number of stale guids dropped.

        """
        import scriptcontext as sc  # type: ignore

        from compas_rhino.objects import find_object

        table = sc.doc.Objects
        find_current = getattr(table, "FindId", None) or table.Find

        dropped = 0
        for sceneobject in self.scene.objects:
            guids = sceneobject._guids
            if not guids:
                continue

            alive = []
            for guid in guids:
                if find_object(guid) is not None:
                    alive.append(guid)  # purge_objects can handle it
                    continue

                # purge_objects would crash on this guid. If the object is
                # nonetheless in the current document, delete it here so the
                # redraw does not leave an untracked copy behind.
                if find_current(guid) is not None:
                    table.Delete(guid, True)
                dropped += 1

            if len(alive) != len(guids):
                sceneobject._guids = alive

        return dropped

    def redraw(self) -> None:
        """Redraw the scene and re-tag Block guids and materials.

        Scene.redraw() recreates every drawn Rhino object, not just newly
        added ones, so guids change on every redraw. Route all redraws
        through here so the "element_guid"/"material_guid" tags never go stale.
        """
        self.prune_stale_guids()
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
        """Tag each Block's Rhino object with its material's guid AND its name.

        The guid is the durable link (names are editable and need not be
        unique); the name is what makes the assignment readable in the Rhino
        properties panel without looking anything up.

        Blocks without an assigned material have both tags removed (passing
        `None` to SetUserText deletes the key) so a stale tag can't survive
        a material being unassigned.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        for sceneobj in self.scene.find_all_by_itemtype(Block):
            material = sceneobj.item.material
            guid_value = str(material.guid) if material is not None else None
            name_value = material.name if material is not None else None
            for guid in sceneobj.guids:
                rs.SetUserText(guid, "material_guid", guid_value)
                rs.SetUserText(guid, "material_name", name_value)

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
    # ...), with one `active_problem` at a time. Each problem owns ONE Rhino
    # layer, "Masonry::<index>_<name>"; its content belongs to the boundary
    # conditions, which create their own subtrees on demand.
    #
    # The Problem object is the source of truth and the Rhino geometry is
    # *derived*: draw_bc() clears and regenerates it, so add/remove/modify only
    # need to mutate the Problem and redraw.

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

    def choose_problem(self, message="Problem", keywords=False):
        """Prompt the user to pick one of the problems.

        Parameters
        ----------
        message : str, optional
            Prompt shown to the user.
        keywords : bool, optional
            If True, offer the problem names as command line options
            (compas_masonry.inputs.choose), with the active problem as the
            Enter default. If False (default), print the problems with an index
            and ask for the index with rs.GetString.

        Returns
        -------
        str or None
            The chosen problem name, or None if there are none / cancelled.

        """
        names = list(self.problems.keys())
        if not names:
            return None
        if len(names) == 1:
            return names[0]

        if keywords:
            from compas_masonry.inputs import choose

            active = self.active_problem_name
            default = active if active in names else names[0]
            return choose(message, names, default=default)

        # rs.GetString option keywords can't contain the "Problem_" underscore
        # reliably across locales, so selection is by printed index.
        import rhinoscriptsyntax as rs  # type: ignore

        for i, n in enumerate(names):
            print(f"{i}: {n}" + ("  (active)" if n == self.active_problem_name else ""))
        idx = rs.GetString(message=f"{message} index", strings=[str(i) for i in range(len(names))])
        if not idx:
            return None
        return names[int(idx)]

    def create_problem(self, model, name=None, source=None):
        """Create (or duplicate) a Problem for `model`, store it, make it active.

        Creates only the problem's own layer, "Masonry::<index>_<name>". Its
        content belongs to the boundary conditions, which add their subtrees on
        demand.

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
            # `boundary_conditions` is a LIST since the compas_dem rename, so copy
            # each BC rather than the list (list.copy() would share the BC objects).
            problem._boundary_conditions = [bc.copy() for bc in source.boundary_conditions]
            problem._contact_properties = source.contact_properties.copy()
            problem._solver = source._solver.copy() if source._solver else None
        else:
            problem.add_supports_from_model(model)

        self.problems[name] = problem
        self.save_problems()
        self.set_active_problem(name)

        self.ensure_indexed_problem_layer(name)

        return problem

    def refresh_problem_supports(self, name, model=None) -> tuple:
        """Re-import the model's supports into a problem, keeping everything else.

        Supports live on `Block.is_support`, are copied onto the Problem when it
        is created, and copied again into each BoundaryCondition when it is
        registered. So editing supports in Model_supports afterwards left the
        problem and its BCs holding the OLD set, with nothing to say so — the
        alternative being to delete the problem and rebuild it.

        Prescribed displacements are left untouched: only the full-fixity
        entries (`is_support`) are replaced.

        Returns
        -------
        tuple[list[int], list[int]]
            The support node indices before and after.

        """
        from compas_masonry.boundaryconditions import is_support

        problem = self.problems.get(name)
        if problem is None:
            return [], []

        model = model or self.get("blockmodel")
        if model is None:
            return list(problem.supports), list(problem.supports)

        before = list(problem.supports)
        after = sorted(block.graphnode for block in model.elements() if block.is_support)

        problem._supports = list(after)

        for bc in problem.boundary_conditions:
            # the property hands back the underlying list, so this edits the BC
            entries = bc.displacements
            kept = [entry for entry in entries if not is_support(entry)]
            entries[:] = kept
            for index in after:
                bc.add_support(index)

        self.save_problems()
        return before, after

    def delete_problem(self, name) -> None:
        """Remove a problem and its Rhino layer subtree.

        The remaining problem layers are renumbered afterwards, so the index
        prefixes stay consecutive.
        """
        from compas_rhino.layers import delete_layers

        layer = self.indexed_problem_layer(name)

        self.problems.pop(name, None)
        self.save_problems()
        if self.active_problem_name == name:
            self.set_active_problem(next(iter(self.problems), None))
        delete_layers([layer])

        self.renumber_problem_layers()

    # =============================================================================
    # Boundary condition layers
    # =============================================================================

    # A BoundaryCondition owns its loads, its prescribed displacements and its
    # results, so a problem has no Loads/Boundary conditions sublayers of its
    # own — only one subtree per BC:
    #
    #   Masonry::1_<problem>::BC1_<bc>::Loads
    #                                 ::Displacements
    #                                 ::Results
    #
    # Layers are created on demand (when a BC is created or drawn), not when the
    # problem is created.
    #
    # compas_dem renamed LoadCase to BoundaryCondition, so this whole block
    # speaks "bc"; the layer prefix is BC<n>_ rather than LC<n>_.

    BC_SUBLAYERS = ["Loads", "Displacements", "Results"]

    # What a boundary condition is FOR. compas_dem's BoundaryCondition has no
    # such field, so it is kept session-side, keyed by problem and BC index.
    #
    # It exists because a BoundaryCondition is created with g=9.81, so every
    # new BC used to show a gravity arrow whether or not it was about gravity.
    # The kind decides what a BC may hold, what is drawn for it, and whether it
    # carries gravity at all.
    BC_KINDS = ["Gravity", "Loads", "Displacements", "Mixed"]
    BC_KIND_DEFAULT = "Mixed"

    def bc_kinds(self, problem_name) -> dict:
        """The {index (str): kind} map of a problem."""
        return (self.setdefault("bc_kinds", dict)).setdefault(problem_name, {})

    def bc_kind(self, problem_name, index) -> str:
        """The kind of one boundary condition (BC_KIND_DEFAULT if never set)."""
        return self.bc_kinds(problem_name).get(str(index), self.BC_KIND_DEFAULT)

    def set_bc_kind(self, problem_name, index, kind) -> None:
        kinds = self.setdefault("bc_kinds", dict)
        kinds.setdefault(problem_name, {})[str(index)] = kind
        self["bc_kinds"] = kinds

    def reindex_bc_kinds(self, problem_name, order) -> None:
        """Rewrite the kind map after the BC list shifts.

        `order` holds the OLD index of each surviving BC, in its new order — so
        deleting BC2 of three passes [0, 2].
        """
        kinds = self.setdefault("bc_kinds", dict)
        current = kinds.get(problem_name, {})
        kinds[problem_name] = {str(new): current.get(str(old), self.BC_KIND_DEFAULT) for new, old in enumerate(order)}
        self["bc_kinds"] = kinds

    # what each kind accepts: "gravity" | "load" | "displacement"
    BC_KIND_ACCEPTS = {
        "Gravity": ("gravity",),
        "Loads": ("load",),
        "Displacements": ("displacement",),
        "Mixed": ("gravity", "load", "displacement"),
    }

    def bc_allows(self, kind, entry) -> bool:
        """Whether a BC of `kind` may hold a "gravity" / "load" / "displacement" entry."""
        return entry in self.BC_KIND_ACCEPTS.get(kind, self.BC_KIND_ACCEPTS[self.BC_KIND_DEFAULT])

    def problem_index(self, name) -> int:
        """1-based position of a problem in the session (0 if unknown)."""
        names = list(self.problems.keys())
        return names.index(name) + 1 if name in names else 0

    def indexed_problem_layer(self, name, sub=None) -> str:
        """Layer path of a problem, prefixed with its index: "Masonry::1_<name>"."""
        leaf = f"{self.problem_index(name)}_{name}"
        return f"Masonry::{leaf}::{sub}" if sub else f"Masonry::{leaf}"

    def ensure_indexed_problem_layer(self, name) -> None:
        """Create the problem layer (no sublayers — boundary conditions add their own)."""
        from compas_rhino.layers import create_layers_from_path

        create_layers_from_path(self.indexed_problem_layer(name), separator="::")

    def renumber_problem_layers(self) -> None:
        """Rename the problem layers so their index prefixes stay consecutive.

        Called after a problem is deleted: "1_A", "3_C" becomes "1_A", "2_C".
        """
        import rhinoscriptsyntax as rs  # type: ignore

        layers = rs.LayerNames() or []
        for index, name in enumerate(self.problems, start=1):
            target = f"{index}_{name}"
            for layer in layers:
                parts = layer.split("::")
                if len(parts) != 2 or parts[0] != "Masonry":
                    continue
                leaf = parts[1]
                if leaf == target:
                    break
                prefix, _, rest = leaf.partition("_")
                if rest == name and prefix.isdigit():
                    rs.RenameLayer(layer, target)
                    break

    def choose_bc(self, problem, message="Boundary condition"):
        """Print the boundary conditions of a problem and prompt for one.

        Returns
        -------
        tuple[int, object] or None
            (index, boundary condition), or None if there are none / cancelled.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import bc_labels

        cases = problem.boundary_conditions
        if not cases:
            return None
        if len(cases) == 1:
            return 0, cases[0]

        labels = bc_labels(problem)
        for label in labels:
            print(label)
        label = rs.ListBox(labels, message=message, title="Boundary conditions")
        if not label:
            return None
        index = int(label.split(":")[0])
        return index, cases[index]

    def choose_bcs(self, problem, message="Boundary conditions to solve"):
        """Pick a combination of boundary conditions (multiple selection).

        Returns
        -------
        list[tuple[int, object]] or None
            The selected (index, boundary condition) pairs, or None if cancelled.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import bc_labels

        cases = problem.boundary_conditions
        if not cases:
            return None

        labels = bc_labels(problem)
        selected = rs.MultiListBox(labels, message=message, title="Boundary conditions")
        if not selected:
            return None

        indices = sorted(int(label.split(":")[0]) for label in selected)
        return [(i, cases[i]) for i in indices]

    def bc_layer(self, problem_name, bc_name, index, sub=None) -> str:
        """Layer path of a boundary condition: "Masonry::1_<problem>::BC1_<bc>"."""
        leaf = f"BC{index + 1}_{bc_name}"
        base = f"{self.indexed_problem_layer(problem_name)}::{leaf}"
        return f"{base}::{sub}" if sub else base

    def ensure_bc_layers(self, problem_name, bc_name, index, subs=None) -> None:
        """Create the layer(s) of one boundary condition (idempotent, on demand).

        Only the BC's own layer is created by default. The Loads / Displacements
        / Results sublayers are made when there is something to put in them
        (`ensure_bc_sublayer`), so an empty BC does not litter the tree with
        three empty layers, and a Gravity BC grows no Displacements layer.

        Pass `subs` to force specific sublayers.
        """
        from compas_rhino.layers import create_layers_from_path

        create_layers_from_path(self.bc_layer(problem_name, bc_name, index), separator="::")
        for sub in subs or []:
            create_layers_from_path(self.bc_layer(problem_name, bc_name, index, sub), separator="::")

    def ensure_bc_sublayer(self, problem_name, bc_name, index, sub) -> str:
        """Create one BC sublayer on demand and return its path."""
        from compas_rhino.layers import create_layers_from_path

        layer = self.bc_layer(problem_name, bc_name, index, sub)
        create_layers_from_path(layer, separator="::")
        return layer

    def clear_bc_layers(self, problem_name, bc_name, index) -> None:
        """Clear the drawn geometry of one boundary condition, keeping the layers.

        Guarded per sublayer: they are created on demand, so most BCs never have
        all three, and `clear_layer` on a missing layer is a no-op anyway.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import clear_layer

        for sub in self.BC_SUBLAYERS:
            layer = self.bc_layer(problem_name, bc_name, index, sub)
            if rs.IsLayer(layer):
                clear_layer(layer)

    def delete_bc_layers(self, problem_name, bc_name, index) -> None:
        """Delete the layer subtree of one boundary condition."""
        from compas_rhino.layers import delete_layers

        delete_layers([self.bc_layer(problem_name, bc_name, index)])

    def delete_all_bc_layers(self, problem_name) -> None:
        """Delete every boundary condition subtree of a problem.

        Used after a delete or rename: the layer name carries the BC index, so
        the surviving layers are dropped and regenerated by draw_problem_bcs
        rather than renamed one by one.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import delete_layers

        parent = self.indexed_problem_layer(problem_name)
        children = rs.LayerChildren(parent) if rs.IsLayer(parent) else None
        if children:
            delete_layers(list(children))

    def draw_bc(self, problem_name, bc, index, model=None) -> None:
        """Clear and redraw the geometry of one boundary condition.

        Loads are arrows under "…::Loads"; prescribed displacements are arrows
        and prescribed rotations are circles around the rotation axis, both
        under "…::Displacements" — no displaced copy of the geometry is drawn
        (that is what Results_show does).

        Fixed supports are skipped: they belong to the model/problem and are
        copied into every boundary condition, and are already drawn red by the
        model layer (Model_supports).
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import bc_name
        from compas_masonry.boundaryconditions import entry_vector
        from compas_masonry.boundaryconditions import is_support

        model = model or self.get("blockmodel")
        if model is None:
            return

        name = bc_name(bc, index)

        self.ensure_bc_layers(problem_name, name, index)
        self.clear_bc_layers(problem_name, name, index)

        gravity_scale, load_scale, disp_scale = self._scales
        blocks = {block.graphnode: block for block in model.elements()}

        # Sublayers are made on first use, so a BC only grows the layers it
        # actually needs: no empty "Displacements" under a gravity-only BC.
        has_loads = bool(bc.g or bc.body_forces or bc.point_loads or bc.surface_loads)
        has_displacements = any(not is_support(entry) for entry in bc.displacements)

        loads_layer = self.ensure_bc_sublayer(problem_name, name, index, "Loads") if has_loads else None
        disp_layer = self.ensure_bc_sublayer(problem_name, name, index, "Displacements") if has_displacements else None

        # --- gravity + global body forces: arrows at the world origin --------
        if bc.g:
            self._draw_bc_vector(loads_layer, "gravity", [0.0, 0.0, 0.0], [0.0, 0.0, -bc.g * gravity_scale], {"g": bc.g})

        for acceleration in bc.body_forces:
            self._draw_bc_vector(
                loads_layer,
                "body_force",
                [0.0, 0.0, 0.0],
                [a * gravity_scale for a in acceleration],
                {"acceleration": acceleration},
            )

        # --- point loads: at the application point, or the block centroid ----
        for entry in bc.point_loads:
            block = blocks.get(entry["block_index"])
            if block is None:
                continue
            force = entry["force"]
            origin = entry.get("point") or list(block.modelgeometry.centroid())
            self._draw_bc_vector(
                loads_layer,
                "point_load",
                origin,
                [f * load_scale for f in force],
                {"force": force, "moment": entry.get("moment"), "loading_type": entry.get("loading_type")},
            )

        # --- surface loads: at the loaded face centroid ----------------------
        for entry in bc.surface_loads:
            block = blocks.get(entry["block_index"])
            if block is None:
                continue
            face_index = entry["face_index"]
            load = entry["load"]
            params = {"load": load, "face_index": face_index, "loading_type": entry.get("loading_type")}

            # the loaded face itself, so it is visible which face carries the
            # load — the arrow alone does not show that
            self._draw_bc_face(loads_layer, "surface_load_face", block, face_index, params)

            self._draw_bc_vector(
                loads_layer,
                "surface_load",
                list(block.modelgeometry.face_centroid(face_index)),
                [f * load_scale for f in load],
                params,
            )

        # --- prescribed displacements/rotations ------------------------------
        for entry in bc.displacements:
            if is_support(entry):
                continue
            block = blocks.get(entry["block_index"])
            if block is None:
                continue

            origin = list(block.modelgeometry.centroid())
            # unconstrained (None) components are drawn as 0.0, never written back
            translation = entry_vector(entry, "translation")
            rotation = entry_vector(entry, "rotation")

            if any(translation):
                self._draw_bc_vector(
                    disp_layer,
                    "displacement",
                    origin,
                    [t * disp_scale for t in translation],
                    {"translation": entry.get("translation")},
                )

            if any(rotation):
                self._draw_rotation_circle(disp_layer, origin, rotation, disp_scale)

        rs.Redraw()

    def draw_problem_bcs(self, problem_name, model=None) -> None:
        """Redraw every boundary condition of a problem."""
        problem = self.problems.get(problem_name)
        if problem is None:
            return
        model = model or self.get("blockmodel")
        for index, bc in enumerate(problem.boundary_conditions):
            self.draw_bc(problem_name, bc, index, model)

    def draw_results(self, problem_name, bc, index, results, model=None, key=None) -> int:
        """Draw the displaced geometry of a Results object under a boundary condition.

        The displaced blocks go under "…::BC<n>_<name>::Results" and carry their
        transformation in User Text. Nothing is drawn by solving — only this
        call (Results_show) puts result geometry in the document.

        The exaggeration comes from `Results.displacement_scale`, which
        compas_dem applies inside `Results.transformation`; it is set here from
        settings.blockmodel.scale_displacement (Session_settings).

        Returns
        -------
        int
            The number of blocks drawn. 0 means the Results carried no
            transformation for any block of the model.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import clear_layer
        from compas_rhino.layers import create_layers_from_path

        from compas_masonry.boundaryconditions import bc_name

        model = model or self.get("blockmodel")
        if model is None or results is None:
            return 0

        name = bc_name(bc, index)
        self.ensure_bc_layers(problem_name, name, index)
        base = self.bc_layer(problem_name, name, index, "Results")
        # One sublayer per solved set ("RBE_BC1-BC2"), so several result sets
        # coexist under the same BC instead of overwriting each other.
        layer = f"{base}::{key}::Displaced" if key else base
        create_layers_from_path(layer, separator="::")

        clear_layer(layer)

        results.displacement_scale = self.settings.blockmodel.scale_displacement

        drawn = 0
        for block in model.elements():
            T = results.transformation(block.graphnode)
            if T is None:
                continue
            mesh = block.modelgeometry.transformed(T)
            vertices, faces = mesh.to_vertices_and_faces()
            guid = rs.AddMesh(vertices, faces)
            if guid is None:
                continue
            rs.ObjectLayer(guid, layer)
            self.set_user_params(
                guid,
                {
                    "problem": problem_name,
                    "boundary_condition": name,
                    "result_kind": "displaced_block",
                    "element_guid": str(block.guid),
                    "transformation": [list(row) for row in T.matrix],
                },
            )
            drawn += 1

        rs.Redraw()
        return drawn

    # =============================================================================
    # Solver executables
    # =============================================================================

    def ensure_solver_path(self) -> str:
        """Make the solver executables findable, and report what was found.

        The CRA/RBE backends go through compas_cra, which builds a pyomo model
        and hands it to `SolverFactory("ipopt")` — a lookup of the `ipopt`
        *executable* on PATH. Rhino launched from the Finder inherits the
        launchd PATH, not a shell one, so a conda-installed ipopt is invisible
        and the solve dies inside pyomo with a message that says nothing about
        PATH.

        `settings.solver_bin` is prepended only when the lookup already fails,
        so a properly configured environment is never overridden.

        Returns
        -------
        str
            The resolved path to `ipopt`, or "" if it is still not found.

        """
        import os
        import shutil

        found = shutil.which("ipopt")
        if found:
            return found

        solver_bin = self.settings.solver_bin
        if solver_bin and os.path.isdir(solver_bin):
            os.environ["PATH"] = solver_bin + os.pathsep + os.environ.get("PATH", "")
            found = shutil.which("ipopt")
            if found:
                return found

        return ""

    # =============================================================================
    # Result forces (CRA / RBE: the answer is on the contacts, not the blocks)
    # =============================================================================

    def draw_result_forces(self, problem_name, bc, index, results, model=None, key=None) -> int:
        """Draw the contact forces of a Results object under a boundary condition.

        CRA and RBE do not move anything — `_post_processing_cra` stores an
        identity transformation per block and puts the whole answer on the
        contact edges. So a displaced-geometry view of a CRA result shows a
        duplicate of the model and looks like nothing happened; this is what
        makes such a result visible.

        Per contact edge: the contact geometry (polygon / line / point,
        matching the contact class) and the resultant as a line **centred** on
        the contact point, so its direction reads without an arrowhead.

        Scaling follows the tested reference viewer (see the plan): at
        `settings.blockmodel.scale_forces == 1.0` the largest resultant in this
        result set is drawn half as long as the biggest block is wide. That is
        relative, not m-per-N, so forces show up whatever the model units are.

        Returns
        -------
        int
            The number of resultants drawn.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import clear_layer
        from compas_rhino.layers import create_layers_from_path

        from compas_masonry.boundaryconditions import bc_name

        model = model or self.get("blockmodel")
        if model is None or results is None:
            return 0

        name = bc_name(bc, index)
        base = self.bc_layer(problem_name, name, index, "Results")
        layer = f"{base}::{key}::Forces" if key else f"{base}::Forces"
        create_layers_from_path(layer, separator="::")
        clear_layer(layer)

        resultants = self._result_resultants(results)
        if not resultants:
            return 0

        magnitudes = [m for _, _, m, _ in resultants]
        largest = max(magnitudes)
        if largest <= 0:
            return 0

        # dimensionless -> absolute: biggest force spans half the biggest block
        scale = self.settings.blockmodel.scale_forces * 0.5 * self._max_block_size(model) / largest

        drawn = 0
        for point, vector, magnitude, edge in resultants:
            if magnitude <= 0:
                continue
            self._draw_contact_geometry(layer, results, edge)
            guid = self._draw_centred_line(layer, point, [c * scale for c in vector])
            if guid is None:
                continue
            self.set_user_params(
                guid,
                {
                    "problem": problem_name,
                    "boundary_condition": name,
                    "result_kind": "contact_resultant",
                    "edge": list(edge),
                    "resultant_global": list(vector),
                    "resultant_local": results.resultant_local(edge),
                    "force_magnitude": magnitude,
                },
            )
            drawn += 1

        rs.Redraw()
        return drawn

    def set_model_transparency(self, transparency=0.0) -> None:
        """Fade the model's blocks, so result geometry reads on top of them.

        Transparency lives in a layer's RENDER MATERIAL, which only shows in
        viewport modes that use render materials (Rendered, Raytraced, or a
        Shaded mode set to "Rendering material"). The stock Shaded mode paints
        everything with its own neutral material, so blocks stay opaque there —
        a Rhino display-pipeline limit, not something this can work around.

        The material name encodes the setting, so a changed value makes a fresh
        material rather than fighting an in-place table update, and an unchanged
        value reuses the existing one. Restore with `transparency=0.0`.

        Parameters
        ----------
        transparency : float
            0.0 = opaque, 1.0 = invisible.

        """
        import System.Drawing  # type: ignore
        import scriptcontext as sc  # type: ignore

        import Rhino  # type: ignore
        from compas_rhino.layers import create_layers_from_path

        for path, color in (("Masonry::Model::Blocks", (170, 170, 170)), ("Masonry::Model::Supports", (230, 40, 30))):
            if not sc.doc.Layers.FindByFullPath(path, -1) >= 0:
                create_layers_from_path(path, separator="::")
            index = sc.doc.Layers.FindByFullPath(path, -1)
            if index < 0:
                continue
            layer = sc.doc.Layers[index]

            name = "{}_{:02x}{:02x}{:02x}_{:.0f}".format(path.replace(":", "_"), color[0], color[1], color[2], transparency * 100)
            material_index = sc.doc.Materials.Find(name, True)
            if material_index < 0:
                material = Rhino.DocObjects.Material()
                material.Name = name
                material.DiffuseColor = System.Drawing.Color.FromArgb(*color)
                material.Transparency = transparency
                material_index = sc.doc.Materials.Add(material)

            layer.RenderMaterialIndex = material_index
            # Rhino 8 reads the RDK render material in Rendered mode; the legacy
            # index above still covers the older display paths.
            try:
                rdk = None
                for content in sc.doc.RenderMaterials:
                    if content.Name == name:
                        rdk = content
                        break
                if rdk is None:
                    rdk = Rhino.Render.RenderMaterial.CreateBasicMaterial(sc.doc.Materials[material_index], sc.doc)
                    sc.doc.RenderMaterials.Add(rdk)
                layer.RenderMaterial = rdk
            except Exception:
                pass  # older Rhino without the RDK API — the legacy index still applies

            try:
                layer.CommitChanges()
            except Exception:
                pass  # Rhino 8 layers commit property changes directly

    def _result_resultants(self, results) -> list:
        """[(point, vector, magnitude, edge), …] for every contact with a force.

        Lives in `compas_masonry.results`, which derives everything the reports
        show from a `Results` without Rhino — the drawing here and the reporting
        commands must agree on the numbers.
        """
        from compas_masonry.results import contact_resultants

        return contact_resultants(results)

    def _draw_contact_geometry(self, layer, results, edge):
        """Draw a contact by its class: polygon, line, or point.

        EdgeContact/VertexContact results carry no polygon, so filtering on
        face contacts alone would silently drop them (same trap as §1.6).
        """
        import rhinoscriptsyntax as rs  # type: ignore

        guid = None
        if results.face_contact(edge):
            polygon = results.contact_polygon(edge)
            if polygon is not None:
                points = [list(p) for p in polygon.points]
                if len(points) > 2:
                    guid = rs.AddPolyline(points + [points[0]])
        elif results.edge_contact(edge):
            line = results.contact_geometry(edge)
            if line is not None:
                guid = rs.AddLine(list(line.start), list(line.end))
        elif results.point_contact(edge):
            points = results.contact_point(edge)
            if points:
                guid = rs.AddPoint(list(points[0]))

        if guid is None:
            return None
        rs.ObjectLayer(guid, layer)
        self.set_user_params(guid, {"result_kind": "contact", "edge": list(edge)})
        return guid

    def _draw_centred_line(self, layer, point, vector):
        """Draw a force resultant as a line centred on `point`, spanning ±v/2."""
        import rhinoscriptsyntax as rs  # type: ignore

        start = [p - 0.5 * v for p, v in zip(point, vector)]
        end = [p + 0.5 * v for p, v in zip(point, vector)]
        if start == end:
            return None
        guid = rs.AddLine(start, end)
        if guid is None:
            return None
        rs.ObjectLayer(guid, layer)
        return guid

    def _max_block_size(self, model=None) -> float:
        """Largest block bounding-box diagonal, the yardstick for force scaling."""
        from compas.geometry import bounding_box

        model = model or self.get("blockmodel")
        largest = 0.0
        for block in model.elements():
            box = bounding_box(block.modelgeometry.vertices_attributes("xyz"))
            diagonal = sum((b - a) ** 2 for a, b in zip(box[0], box[6])) ** 0.5
            largest = max(largest, diagonal)
        return largest or 1.0

    def _draw_bc_vector(self, layer, kind, origin, vector, params=None):
        """Draw an arrow on a boundary condition layer and tag it."""
        import rhinoscriptsyntax as rs  # type: ignore

        end = [o + v for o, v in zip(origin, vector)]
        if end == list(origin):
            return None
        guid = rs.AddLine(origin, end)
        rs.CurveArrows(guid, 2)
        rs.ObjectLayer(guid, layer)
        tags = {"load_kind": kind}
        tags.update(params or {})
        self.set_user_params(guid, tags)
        return guid

    def _draw_bc_face(self, layer, kind, block, face_index, params=None):
        """Draw a copy of a loaded block face as a mesh, on a boundary condition layer."""
        import rhinoscriptsyntax as rs  # type: ignore

        polygon = block.modelgeometry.face_polygon(face_index)
        vertices = [list(point) for point in polygon.points]
        if len(vertices) < 3:
            return None

        guid = rs.AddMesh(vertices, [list(range(len(vertices)))])
        if guid is None:
            return None

        rs.ObjectLayer(guid, layer)
        tags = {"load_kind": kind}
        tags.update(params or {})
        self.set_user_params(guid, tags)
        return guid

    def _draw_rotation_circle(self, layer, origin, rotation, scale):
        """Draw a prescribed rotation as a circle around its axis."""
        import rhinoscriptsyntax as rs  # type: ignore

        from compas.geometry import Plane
        from compas.geometry import Vector
        from compas_rhino.conversions import plane_to_rhino

        axis = Vector(*rotation)
        angle = axis.length
        if not angle:
            return None

        plane = Plane(origin, axis.unitized())
        guid = rs.AddCircle(plane_to_rhino(plane), angle * scale)
        if guid is None:
            return None
        rs.ObjectLayer(guid, layer)
        self.set_user_params(guid, {"load_kind": "rotation", "rotation": rotation, "applied_angle_rad": angle * scale})
        return guid

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
