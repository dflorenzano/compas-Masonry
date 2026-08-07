from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_session.lazyload import LazyLoadSession

from .settings import MasonrySettings


class MasonrySession(LazyLoadSession):
    settingsclass = MasonrySettings
    settings: MasonrySettings  # type: ignore

    # How many states history keeps. LazyLoadSession defaults to 53, and every
    # record is a FULL copy of the session's data directory — not a diff — so the
    # depth multiplies the whole model, every problem and every stored result set
    # by that number on disk. 10 is a working figure, not a measured one; measure
    # with a real model before raising it.
    _depth = 10

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

    @property
    def analysis(self):
        """The Analysis: the BlockModel plus every Problem defined over it.

        Created empty on first access. Read through `get()`, NEVER `setdefault()`
        — `setdefault` does not consult the disk (`if key not in self.data`), so on
        a cold cache it would write an empty Analysis straight over a real one and
        destroy the model and every problem with it. That is the trap documented in
        `wiki_session_primer.md` §8.6, and this key is now the one place where it
        would cost everything at once.
        """
        from compas_dem.models import Analysis

        analysis = self.get("analysis")
        if analysis is None:
            analysis = Analysis(name="COMPAS-Masonry")
            self["analysis"] = analysis
        return analysis

    @property
    def model(self):
        """The session BlockModel, or None if no model has been created yet."""
        return self.analysis.model

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

        # Deleting `analysis` drops the model AND every problem in one move — they
        # are one object now, and a problem without its model is exactly the stale
        # state this used to leave behind when only some of the keys were cleared.
        for key in ("analysis", "active_problem", "results", "shown_results"):
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

    # Session keys the plugin owns.
    #
    # `analysis` holds the model AND every problem defined over it, in one
    # `compas_dem.models.Analysis`. It replaced the separate `blockmodel` and
    # `problems` keys on 2026-08-07, because a Problem serializes as a guid
    # REFERENCE to its model: two keys meant every load path had to hand the model
    # back by hand (`_bind_model`) and every one that forgot produced problems that
    # raised on `problem.model` only at solve time. `Analysis.__from_data__` calls
    # `problem.load_model()` for us, so that whole class of bug is gone.
    #
    # The cost, and it is real: one key means `set()` re-serializes the MODEL too
    # on every problem edit — measured at 0.45s for a 6.5 MB BlockModel — where
    # the old `problems` key wrote kilobytes. Accepted deliberately; if it bites,
    # the fix is a dirty-flag on the analysis, not a second key.
    #
    # `results` is still its own key. It moves into the Analysis in a later pass.
    SESSION_KEYS = [
        "analysis",
        "active_problem",
        "results",
        # WHICH results are on screen, written by Results_show. Solving draws
        # nothing, so this is the only record of it — and a restore clears the whole
        # layer tree, so without it every undo silently destroyed the result view.
        "shown_results",
        "envelope",
        "formdiagram",
    ]

    def clear_all(self) -> None:
        """Empty the session: scene objects, every session key, every layer.

        `clear_model` only handles the model layers, so problems, boundary
        conditions and results used to survive a "clear session" both as
        Rhino geometry and as session state. Clearing the ROOT layer with
        `include_children` sweeps the whole tree, including any orphans left
        behind by an earlier crash, and deleting it removes the layers too.

        Rhino refuses to delete the CURRENT layer, and `delete_layers` only
        guards the path it is handed — so with a problem or BC layer current,
        `rs.PurgeLayer("Masonry")` left the whole branch containing it standing,
        which is how problem layers survived a clear. The current layer is moved
        to Default first, and the empty root is recreated afterwards so the next
        command draws into the tree it expects.
        """
        self._clear_document()

        for key in self.SESSION_KEYS:
            self.delete(key)

    def _clear_document(self) -> None:
        """Remove everything the plugin drew, leaving session state untouched.

        Split out of `clear_all` for undo/redo. A restore has just put the
        previous state's files back on disk, and `clear_all`'s `delete(key)` loop
        would unlink exactly those files — so a restore needs the document
        emptied and the data left alone. `clear_all` is that plus the deletion.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        import compas_rhino.layers

        # obj.clear() purges guids through the same path as a redraw, so a guid
        # Rhino can no longer resolve would raise here — prune first (§1.7 rule 1).
        self.prune_stale_guids()

        for sceneobject in list(self.scene.objects):
            # clear() before remove(): removing first drops the guids from the
            # scene while the Rhino objects live on, untracked (§1.7 rule 2).
            sceneobject.clear()
            self.scene.remove(sceneobject)

        self._release_current_layer()

        compas_rhino.layers.clear_layer(self.ROOT_LAYER)
        compas_rhino.layers.delete_layers([self.ROOT_LAYER])

        # start from a clean root rather than from nothing
        compas_rhino.layers.create_layers_from_path(self.ROOT_LAYER, separator="::")
        rs.Redraw()

    def _release_current_layer(self) -> None:
        """Make sure no layer under ROOT_LAYER is the current one.

        Rhino cannot delete the current layer. Anything under "Masonry" being
        current therefore blocks part of the teardown, so the current layer is
        parked on Default (created if the document somehow has no such layer).
        """
        import rhinoscriptsyntax as rs  # type: ignore

        current = rs.CurrentLayer()
        if not current or not (current == self.ROOT_LAYER or current.startswith(self.ROOT_LAYER + "::")):
            return

        if not rs.IsLayer("Default"):
            rs.AddLayer("Default")
        rs.CurrentLayer("Default")

    # =============================================================================
    # History (undo / redo)
    # =============================================================================
    #
    # LazyLoadSession implements half of this. `record()` works: it dumps the working
    # copy and photocopies it into `__records/<timestamp>/`. `undo()` and `redo()` move
    # the FILES back and stop — they never touch `_data` or `_scene`. And `get()` only
    # reads from disk when a key is MISSING from `_data`, so every already-loaded key
    # keeps returning the pre-undo object and the restored file is never opened: undo
    # changes nothing observable. The module's own header comment lists the missing
    # steps ("clear data dict", "load scene ... link items by guid"); neither was written.
    #
    # The second half is added here, and deliberately NOT the way that comment
    # describes it. `_scene.json` is never loaded back, because `Scene.__data__`
    # re-serializes the ITEMS: a reloaded scene object's `.item` would be a copy of the
    # model's block rather than the block itself, so setting `is_support` on the model
    # would stop colouring the block, silently. `SceneObject.settings` also carries no
    # `layer` or `group`. The scene is rebuilt from the restored data instead — the same
    # path Session_import already takes. See temp/wiki_session_primer.md §8.4.

    def record(self, name: str) -> None:
        """Snapshot the current state. Fixes three things the parent gets wrong.

        **1. The persisted cursor is one behind.** `LazyLoadSession.record` writes
        `_history.json` through `dump()` BEFORE it updates `_current`. Inside one
        process that never shows, because `_current` is corrected in memory a line
        later. It shows here because a Rhino command is a fresh `Session(...)` every
        time and `__init__` calls `load_history()`, which reads the stale cursor
        back. `record()` then discards the "forward branch" against it::

            if self.current < len(self.history) - 1:
                self.history[:] = self.history[: self.current + 1]

        A real branch discard, correct in itself — but aimed at a cursor stuck at 0
        it truncates on EVERY command. The list never grew past two entries and undo
        answered "Nothing more to undo!" no matter how much work had been done.
        Re-dumping the history is enough: `_current` is correct by the time the
        parent returns, and `_history.json` is not part of a snapshot (a record
        folder holds only `data/` and the four `_*.json` state files), so writing it
        again cannot disturb the record just taken.

        **2. Dropped records leak their folders.** Both places the parent shortens
        the history — the branch discard above and the depth trim,
        `self.history[:] = self.history[h - self.depth:]` — do it with a slice
        assignment and never delete the folders. `clear_history()` cannot reach them
        afterwards either, because it iterates the LIST. The depth trim runs on
        every record past `_depth`, so the orphans grow without bound: one full copy
        of the session per command, ~6.5 MB each on a real model.

        **3. The data is serialized twice per command.** `dump()` re-serializes
        every key in `_data` to the paths `set()` has already autosynced —
        byte-identical files, and measured at 0.45s per command on a 6.5 MB
        BlockModel, against 3ms for the copy that follows. Emptying the cache around
        the call skips that loop; the working copy on disk is what gets snapshotted
        either way, and scene/settings/tolerance/version are still written because
        they do not come from `_data`.

        That last one makes the snapshot exactly the working copy, which is the rule
        already in force: mutate something reached through `session[...]` and you
        must re-set the key or it is not on disk at all (hence `save_analysis`).
        Anything breaking that rule was already missing from `data/`. It is skipped
        when `autosync` is off, because then the working copy really is stale and
        the full dump is the only thing writing it.

        **4. The scene is serialized too, and nothing ever reads it.** A snapshot
        deliberately carries an EMPTY `_scene.json` — see the comment on the swap
        below for why, and for how to reverse the decision.
        """
        import shutil

        before = {record for record, _ in self.history}

        # A SNAPSHOT DELIBERATELY CARRIES AN EMPTY SCENE.
        #
        # `_scene.json` has no reader. The `scene` property only loads the file when
        # `_scene` is falsy, an empty Scene is truthy (it defines neither `__len__`
        # nor `__bool__`), and `__new__` always assigns one — so that branch can
        # never fire. And the restore rebuilds the scene from the data on purpose,
        # because `Scene.__data__` re-serializes the ITEMS: reloading it would give
        # every scene object a COPY of the model's block instead of the block
        # itself, and lose `layer` and `group` besides (§8.4 of the primer).
        #
        # Writing the real one therefore costs a full object-graph walk over every
        # block, at roughly twice the bytes of the model (12.7 MB against 6.5 MB on
        # a real file), on every single command, for a file nothing will ever open.
        # An empty scene keeps the path present so `undo()`'s `shutil.copy` of it
        # cannot raise FileNotFoundError, and costs nothing to produce.
        #
        # TO REVERSE THIS — if a snapshot is ever wanted to carry a real scene —
        # delete the two swap lines below and their `finally`, leaving:
        #
        #     if self.settings.autosync:
        #         data, self._data = self._data, {}
        #         try:
        #             super().record(name)
        #         finally:
        #             self._data = data
        #     else:
        #         super().record(name)
        #
        # That alone only makes the file real again; ACTUALLY restoring from it
        # additionally needs `_restore_data`/`_redraw_state` to call `load_scene()`
        # and then relink every scene object's item to the matching data item by
        # guid, and reassign `layer` and `group` — the work §8.4 explains and the
        # reason the scene is rebuilt rather than reloaded in the first place.
        # The replacement inherits the live scene's context rather than letting
        # `Scene()` re-detect it: detection reaches for `scriptcontext.doc`, which
        # is a Rhino global, and the context is a property of the session rather
        # than of this one throwaway object.
        scene = self._scene
        self._scene = self.sceneclass(context=scene.context)
        try:
            if self.settings.autosync:
                data, self._data = self._data, {}
                try:
                    super().record(name)
                finally:
                    self._data = data
            else:
                super().record(name)
        finally:
            self._scene = scene

        for dropped in before - {record for record, _ in self.history}:
            shutil.rmtree(self.recordsdir / dropped, ignore_errors=True)

        self.dump_history()

    def ensure_baseline(self) -> None:
        """Record an "Initial state" snapshot if history is empty.

        `undo()` refuses at `current == 0`, so the oldest entry in history is a
        floor rather than a destination — it can never be returned to. Without a
        baseline recorded before the first change, the first command of a session
        is therefore permanently un-undoable.

        Call at the TOP of a recording command, before it mutates anything: the
        baseline has to capture the state as it was BEFORE the first action, which
        is why it cannot be folded into the `record()` at the end.
        """
        if not self.history:
            self.record("Initial state")

    def undo(self) -> bool:
        """Step one state back, and rebuild memory and the document to match.

        Returns
        -------
        bool
            False if there was nothing to undo, in which case nothing was touched.

        """
        if not super().undo():
            return False
        self._restore_state()
        return True

    def redo(self) -> bool:
        """Step one state forward, and rebuild memory and the document to match.

        Returns
        -------
        bool
            False if there was nothing to redo, in which case nothing was touched.

        """
        if not super().redo():
            return False
        self._restore_state()
        return True

    def _restore_state(self) -> None:
        """Rebuild memory and the Rhino document from the record now on disk.

        Called after the parent's undo/redo has swapped the files. Split in two,
        because the half that can silently destroy data needs no Rhino and the
        half that needs Rhino cannot destroy anything: `_restore_data` is
        therefore testable headless, and `tests/test_session_history.py` pins it.
        """
        self._restore_data()
        self._redraw_state()

    def _restore_data(self) -> None:
        """Reload the session from the record now on disk. No Rhino, no drawing.

        The order is not arbitrary:

        1. Drop the in-memory cache, so the next `get()` re-reads a restored file
           instead of returning the object from before the step.
        2. Prime every session key straight away — see the warning below.
        3. Rebuild settings explicitly, because `load_settings()` cannot.
        4. Rebind every problem to the restored model.

        """
        import compas

        self._data.clear()

        # PRIME BEFORE TOUCHING ANY PROPERTY. A key read through anything other
        # than `get()` does NOT consult the disk — the `analysis` property creates
        # an empty Analysis when it finds nothing cached, and on a cold cache that
        # would autosync straight over the analysis.json just restored, taking the
        # model and every problem with it. `get()` is the only accessor that falls
        # through to the file, so it has to run first.
        for key in self.SESSION_KEYS:
            self.get(key)

        # `dump()` writes `settings.model_dump()`, a plain dict, but `load_settings()`
        # hands that straight to the `settings` setter, which requires a settingsclass
        # instance and raises ValueError. So the instance is constructed here rather
        # than calling load_settings().
        if self.settingsfile.exists():
            self._settings = self.settingsclass(**compas.json_load(self.settingsfile))

        # Nothing to rebind. A Problem still serializes as a guid REFERENCE to its
        # model, but `Analysis.__from_data__` calls `problem.load_model()` for every
        # problem it deserializes — which is the whole reason the model and the
        # problems share one key.

    def _redraw_state(self) -> None:
        """Empty the document and redraw it from the restored session data.

        `_clear_document`, not `clear_all`: the data has just been restored and
        `clear_all` would delete the very keys and files this is drawing from.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        self._clear_document()

        model = self.model
        if model is not None:
            self.draw_model()

        for name in self.problems:
            self.ensure_indexed_problem_layer(name)
            self.draw_problem_conditions(name, model)

        self.draw_shown_results(model)

        rs.Redraw()

    def draw_shown_results(self, model=None) -> int:
        """Redraw the result geometry `Results_show` had on screen.

        Result geometry is the one thing a restore cannot infer from the data.
        Solving draws nothing — `Results_show` does, and it takes choices (which
        result keys, and Forces / Displaced / Both) that live nowhere but in the
        document. `_clear_document` destroys the document. So `Results_show`
        records what it drew under "shown_results", and this replays it.

        Keys that are not in the restored `results` are skipped rather than
        reported: undoing to before a solve is *supposed* to take its geometry
        with it, and the key naming it survives only because it is a record of
        intent, not of data.

        The fade is not recorded. `fade_model()` defaults its amount to
        `settings.blockmodel.results_model_transparency`, which is where the
        setting belongs and where it is heading.

        Returns
        -------
        int
            The number of result objects drawn.

        """
        shown = self.get("shown_results") or {}
        model = model or self.model
        if not shown or model is None:
            return 0

        stored = self.get("results") or {}

        drawn = 0
        for problem_name, view in shown.items():
            available = stored.get(problem_name) or {}
            mode = view.get("mode", "Forces")
            for key in view.get("keys", []):
                results = available.get(key)
                if results is None:
                    continue
                if mode in ("Forces", "Both"):
                    drawn += self.draw_result_forces(problem_name, results, model, key=key)
                if mode in ("Displaced", "Both"):
                    drawn += self.draw_results(problem_name, results, model, key=key)

        if drawn:
            # the blocks were just redrawn by draw_model, so they carry their layer
            # colour again and the fade has to be re-applied on top
            self.fade_model()

        return drawn

    def set_model(self, model) -> None:
        """Install `model` as the session BlockModel and draw it.

        Clears the previous model (and dependent problem/results) first.
        This is the shared tail of every model-creating command
        (Model_blocks, Session_import, TNA_blockexports, ...).

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`

        """
        from compas_dem.models import Analysis

        # A FRESH Analysis, not `analysis.set_model(model)`: that would call
        # `problem.load_model()` on every problem still registered, and each one
        # raises because its `model_id` belongs to the model being replaced. The
        # problems are invalid anyway — `clear_model` has just deleted them — so
        # starting a new analysis says that plainly instead of raising.
        self.clear_model()
        self["analysis"] = Analysis(model=model, name="COMPAS-Masonry")
        self.draw_model()

    def save_model(self) -> None:
        """Persist in-place edits to the model (supports, materials, contacts).

        The model lives inside the analysis, so this is `save_analysis` under a
        name that says what the caller changed.
        """
        self.save_analysis()

    def draw_model(self) -> None:
        """Draw the session BlockModel: blocks, and (if contacts have been
        computed) the interaction graph and contact interfaces."""
        model = self.model
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
        model = self.model
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

        model = model or self.model
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
        model = model or self.model
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
    # *derived*: draw_problem_conditions() clears and regenerates it, so
    # add/remove/modify only need to mutate the Problem and redraw.

    # Display scales now live in settings.blockmodel (scale_loads /
    # scale_gravity / scale_displacement) so they're tunable in Session_settings.

    @property
    def _scales(self):
        bm = self.settings.blockmodel
        return bm.scale_gravity, bm.scale_loads, bm.scale_displacement

    @property
    def problems(self) -> dict:
        """The Problems of the analysis, keyed by name, in registration order.

        DERIVED, and therefore read-only: the analysis owns a LIST, and this dict
        is rebuilt on every access. Assigning into it (`session.problems[name] = p`)
        writes to a throwaway and is silently lost — use `add_problem` /
        `remove_problem`, which write through to the analysis.

        Problem names are assumed unique; `next_problem_name` and
        `create_problem` are what keep them so.
        """
        return {problem.name: problem for problem in self.analysis.problems}

    def add_problem(self, problem) -> None:
        """Register a problem on the analysis and persist it.

        `Analysis.add_problem` also loads the analysis model into the problem, so
        the model reference is bound from this moment rather than at the next
        deserialization.
        """
        self.analysis.add_problem(problem)
        self.save_analysis()

    def remove_problem(self, name) -> bool:
        """Drop a problem from the analysis by name. True if one was removed."""
        for problem in list(self.analysis.problems):
            if problem.name == name:
                # `Analysis.problems` is a plain list attribute with no remove
                # method of its own.
                self.analysis.problems.remove(problem)
                self.save_analysis()
                return True
        return False

    @staticmethod
    def solver_of(problem):
        """The Solver configured on a problem, or None.

        compas_dem's `Problem` has `set_solver()` and a private `_solver`, but no
        public getter — so this is the one place that reaches for the private
        attribute, rather than every command doing it and having to explain why.
        Callable without an instance: `MasonrySession.solver_of(problem)`.
        """
        return getattr(problem, "_solver", None)

    def save_analysis(self) -> None:
        """Re-set the analysis key so autosync dumps the mutated objects to disk.

        Replaced `save_problems`. Mutating a Problem in place changes nothing on
        disk — the session is a cache in front of files and only `set()` writes —
        and now that the model travels in the same key, this rewrites the model
        too. See the note on SESSION_KEYS about what that costs.
        """
        self["analysis"] = self.analysis

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
            # `boundary_conditions` is a LIST, so copy each BC rather than the list
            # (list.copy() would share the BC objects).
            problem._boundary_conditions = [bc.copy() for bc in source.boundary_conditions]
            problem._contact_properties = source.contact_properties.copy()
            problem._solver = source._solver.copy() if source._solver else None

        # Nothing else to seed. Supports live on the model (`Block.is_support`) and
        # the solvers read them from there, so a problem never carries a copy —
        # which is why `add_supports_from_model` and the whole refresh dance that
        # kept those copies in step are both gone.

        self.add_problem(problem)
        self.set_active_problem(name)

        self.ensure_indexed_problem_layer(name)

        return problem

    # `refresh_problem_supports` lived here until the 2026-08 compas_dem
    # restructure. It re-imported `Block.is_support` into a problem and into every
    # boundary condition, because supports were copied onto the Problem at creation
    # and into each BC at registration — so editing them afterwards left stale
    # copies behind. Supports are now read from the model by the solvers and are
    # never copied anywhere, so there is nothing to refresh and nothing to go
    # stale. `Model_supports` lost its refresh prompt with it.

    def delete_problem(self, name) -> None:
        """Remove a problem and its Rhino layer subtree.

        The remaining problem layers are renumbered afterwards, so the index
        prefixes stay consecutive.
        """
        from compas_rhino.layers import delete_layers

        layer = self.indexed_problem_layer(name)

        self.remove_problem(name)
        if self.active_problem_name == name:
            self.set_active_problem(next(iter(self.problems), None))
        # Rhino will not delete the current layer, and it is very likely to be
        # one of these — the user just drew into them.
        self._release_current_layer()
        delete_layers([layer])

        self.renumber_problem_layers()

    # =============================================================================
    # Boundary condition layers
    # =============================================================================

    # A PROBLEM IS THE LOAD CASE. Since the 2026-08 compas_dem restructure there is
    # no named BoundaryCondition container to group by — boundary conditions are
    # typed objects (Load / Displacement subclasses) registered directly on the
    # problem — so the BC<n>_<name> level is gone and the two sublayers hang off the
    # grouping layer directly:
    #
    #   Masonry::1_<problem>::BoundaryConditions::Loads
    #                                           ::Displacements
    #                       ::Results::<key>::Forces
    #                                       ::Displaced
    #
    # The BoundaryConditions layer is kept as a grouping node so the problem's own
    # children stay readable, even though it now holds exactly two.
    #
    # Layers are created on demand (when something is drawn into them), not when the
    # problem is created.

    # There is no fixed list of condition sublayers. A group layer is named after
    # the conditions it holds ("Load_1", "Wind", "Displacement_2"), created when
    # the first condition of that group is drawn and deleted when the last one
    # goes, so the set is discovered from the problem rather than declared here.
    BC_PARENT_LAYER = "BoundaryConditions"
    RESULTS_LAYER = "Results"

    # =============================================================================
    # Palette
    # =============================================================================

    # Set as a CUSTOM OBJECT COLOUR on each object as it is drawn, not as a layer
    # colour. Object colour is what every display mode honours — a layer colour
    # is overridden the moment anything sets an object colour, and a layer render
    # material only shows in Rendered/Raytraced (which is what made the old
    # fading invisible in stock Shaded).
    COLOR_FORCE = (21, 128, 61)  # contact resultants and applied loads
    COLOR_REACTION = (214, 40, 40)  # resultants on a support contact
    COLOR_DISPLACEMENT = (0, 0, 0)  # prescribed translations and rotations
    COLOR_CONTACT = (0, 146, 210)  # contact surfaces, edge lines and points (0092d2)
    COLOR_FADED_BLOCK = (200, 200, 200)  # blocks while results are drawn on top

    # The BC-KIND MAP lived here — `BC_KINDS`, `bc_kind`, `set_bc_kind`,
    # `reindex_bc_kinds`, `bc_allows` and the `bc_kinds` session key. It existed for
    # two reasons, and the 2026-08 compas_dem restructure removed both:
    #
    #   - a BoundaryCondition was constructed with g=9.81, so every new one arrived
    #     carrying a gravity load nobody asked for. `g` is gone; self-weight is
    #     applied unconditionally from block density.
    #   - a BC was an untyped bag that could hold anything, so what it was FOR had
    #     to be tracked beside it. A BC is now a typed object — the class IS the
    #     kind — and it was keyed by list index, which meant reindexing the map
    #     every time a BC was deleted.
    #
    # Nothing replaces it. `boundaryconditions.is_load` / `is_displacement` answer
    # the same question from the object itself.

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

    def choose_boundary_condition(self, problem, message="Boundary condition"):
        """Print the boundary conditions of a problem and prompt for one.

        Replaces `choose_bc`. There is no BC container to pick any more — this
        picks one *entry*, which is what Remove operations need.

        Returns
        -------
        tuple[int, object] or None
            (index, boundary condition), or None if there are none / cancelled.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import bc_labels

        conditions = problem.boundary_conditions
        if not conditions:
            return None

        labels = bc_labels(problem)
        for label in labels:
            print(label)
        label = rs.ListBox(labels, message=message, title="Boundary conditions")
        if not label:
            return None
        index = int(label.split(":")[0])
        return index, conditions[index]

    def choose_boundary_conditions(self, problem, message="Boundary conditions"):
        """Pick several boundary conditions at once (for bulk removal).

        `choose_bcs` used to pick which BCs to *solve*. That selection is gone —
        every boundary condition on a problem is solved, and a different set means
        a different problem — so this is only used for editing now.

        Returns
        -------
        list[tuple[int, object]] or None

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import bc_labels

        conditions = problem.boundary_conditions
        if not conditions:
            return None

        selected = rs.MultiListBox(bc_labels(problem), message=message, title="Boundary conditions")
        if not selected:
            return None

        indices = sorted(int(label.split(":")[0]) for label in selected)
        return [(i, conditions[i]) for i in indices]

    def bc_parent_layer(self, problem_name) -> str:
        """Grouping layer for a problem's conditions: "…::BoundaryConditions"."""
        return f"{self.indexed_problem_layer(problem_name)}::{self.BC_PARENT_LAYER}"

    def bc_layer(self, problem_name, group=None) -> str:
        """Layer path of one boundary-condition GROUP.

        "Masonry::1_<problem>::BoundaryConditions::Load_1". A group is the set of
        conditions sharing a name (`boundaryconditions.group_name`), so adding a
        load either extends an existing layer or starts a new one — which is the
        separation the fixed Loads/Displacements pair could not express.
        """
        base = self.bc_parent_layer(problem_name)
        return f"{base}::{group}" if group else base

    def results_layer(self, problem_name, key=None, sub=None) -> str:
        """Layer path of a problem's results: "Masonry::1_<problem>::Results::<key>::<sub>".

        The key is the same one the session stores the result under — the solver
        plus a timestamp, so re-solving never overwrites an earlier run.
        """
        base = f"{self.indexed_problem_layer(problem_name)}::{self.RESULTS_LAYER}"
        if key:
            base = f"{base}::{key}"
        return f"{base}::{sub}" if sub else base

    def ensure_bc_sublayer(self, problem_name, group) -> str:
        """Create one group's layer on demand and return its path.

        On demand, so a problem only grows the group layers it actually holds.
        """
        from compas_rhino.layers import create_layers_from_path

        layer = self.bc_layer(problem_name, group)
        create_layers_from_path(layer, separator="::")
        return layer

    def clear_bc_layers(self, problem_name) -> None:
        """Clear every drawn condition of a problem, keeping the group layers.

        Group layers are user-named and created on demand, so the set cannot be
        hardcoded — clear the parent with `include_children`, which sweeps all of
        them in one pass and is a no-op if the parent does not exist.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import clear_layer

        parent = self.bc_parent_layer(problem_name)
        if rs.IsLayer(parent):
            clear_layer(parent)  # include_children=True by default

    def delete_bc_group_layer(self, problem_name, group) -> None:
        """Delete one group's layer, after its last condition is removed."""
        from compas_rhino.layers import delete_layers

        self._release_current_layer()
        delete_layers([self.bc_layer(problem_name, group)])

    def prune_bc_group_layers(self, problem_name) -> int:
        """Delete group layers that no longer correspond to a group on the problem.

        A group only exists while something carries its name, so removing the last
        condition of a group has to take its layer with it — otherwise the tree
        accumulates empty layers that look like live groups.

        Returns
        -------
        int
            The number of layers deleted.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_rhino.layers import delete_layers

        from compas_masonry.boundaryconditions import group_names

        problem = self.problems.get(problem_name)
        if problem is None:
            return 0

        parent = self.bc_parent_layer(problem_name)
        if not rs.IsLayer(parent):
            return 0

        live = set(group_names(problem))
        stale = [layer for layer in (rs.LayerChildren(parent) or []) if layer.split("::")[-1] not in live]
        if stale:
            self._release_current_layer()
            delete_layers(stale)
        return len(stale)

    def delete_bc_layers(self, problem_name) -> None:
        """Delete a problem's whole BoundaryConditions subtree.

        Results are a sibling of that subtree, not a child, so this never takes a
        result set with it.
        """
        from compas_rhino.layers import delete_layers

        parent = self.bc_parent_layer(problem_name)
        self._release_current_layer()
        delete_layers([parent])

    def draw_problem_conditions(self, problem_name, model=None) -> None:
        """Clear and redraw every boundary condition of a problem.

        Replaces `draw_bc` / `draw_problem_bcs`. A problem IS the load case, so
        there is nothing to iterate above the conditions themselves.

        Loads become arrows under "…::BoundaryConditions::Loads"; prescribed
        movements become arrows (translation) and circles around the rotation axis
        (rotation) under "…::BoundaryConditions::Displacements". No displaced copy
        of the geometry is drawn — that is what Results_show does.

        Dispatch is on the CLASS of each condition, which is where the meaning now
        lives. Supports are not drawn here at all: they are a model concern
        (`Block.is_support`) and are already drawn red on the model layer.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import anchor_point
        from compas_masonry.boundaryconditions import components
        from compas_masonry.boundaryconditions import group_name

        problem = self.problems.get(problem_name)
        if problem is None:
            return

        model = model or self.get("blockmodel")
        if model is None:
            return

        self.clear_bc_layers(problem_name)
        self.prune_bc_group_layers(problem_name)

        gravity_scale, load_scale, disp_scale = self._scales
        blocks = {block.graphnode: block for block in model.elements()}

        # One layer per GROUP, created on first use. The group is the condition's
        # own name, so "add to Wind" and "add to Live" land on different layers
        # without anything session-side tracking which is which.
        group_layers = {}

        def layer_for(bc):
            group = group_name(bc)
            if group not in group_layers:
                group_layers[group] = self.ensure_bc_sublayer(problem_name, group)
            return group_layers[group]

        for bc in problem.loads:
            loads_layer = layer_for(bc)
            kind = type(bc).__name__

            # --- BodyForce: global, so drawn once at the world origin ---------
            if kind == "BodyForce":
                self._draw_bc_vector(
                    loads_layer,
                    "body_force",
                    [0.0, 0.0, 0.0],
                    [a * gravity_scale for a in bc.acceleration],
                    {"acceleration": bc.acceleration, "loading_type": bc.loading_type},
                )
                continue

            block = blocks.get(bc.block)
            if block is None:
                continue

            # --- PointLoad: at its resolved anchor ----------------------------
            if kind == "PointLoad":
                origin = anchor_point(bc, block)
                if origin is None:
                    continue
                self._draw_bc_vector(
                    loads_layer,
                    "point_load",
                    origin,
                    [f * load_scale for f in bc.force],
                    {
                        "force": bc.force,
                        "anchor": bc.anchor,
                        "anchor_value": bc.anchor_value,
                        "loading_type": bc.loading_type,
                    },
                )

            # --- Moment: a circle about its axis, like a prescribed rotation ---
            elif kind == "Moment":
                self._draw_rotation_circle(
                    loads_layer,
                    list(block.modelgeometry.centroid()),
                    [m * load_scale for m in bc.moment],
                    1.0,
                    kind="moment",
                    color=self.COLOR_FORCE,
                )

            # --- SurfaceLoad: the loaded face, plus a traction arrow ----------
            elif kind == "SurfaceLoad":
                params = {"traction": bc.traction, "face_index": bc.face, "loading_type": bc.loading_type}
                # the face itself, so which face carries the load is visible —
                # the arrow alone does not show that
                self._draw_bc_face(loads_layer, "surface_load_face", block, bc.face, params)
                self._draw_bc_vector(
                    loads_layer,
                    "surface_load",
                    list(block.modelgeometry.face_centroid(bc.face)),
                    [f * load_scale for f in bc.traction],
                    params,
                )

        for bc in problem.displacements:
            block = blocks.get(bc.block)
            if block is None:
                continue

            disp_layer = layer_for(bc)
            origin = list(block.modelgeometry.centroid())
            # unconstrained (None) components draw as 0.0, never written back
            vector = components(bc)
            if not any(vector):
                continue

            if type(bc).__name__ == "Rotation":
                self._draw_rotation_circle(disp_layer, origin, vector, disp_scale)
            else:
                self._draw_bc_vector(
                    disp_layer,
                    "displacement",
                    origin,
                    [v * disp_scale for v in vector],
                    {"components": list(getattr(bc, "components", vector))},
                )

        rs.Redraw()

    def count_results(self) -> int:
        """How many result sets are stored, across every problem.

        `results` is `{problem_name: {result_key: Results}}`, so the count is the
        number of solver runs held, not the number of problems.
        """
        stored = self.get("results") or {}
        return sum(len(sets) for sets in stored.values())

    def clear_results(self) -> int:
        """Delete every stored result set, and the Rhino geometry drawn from it.

        Called when something invalidates the results rather than merely changing
        them — recomputing contacts, for one: a `Results` is keyed by graph node
        index and by `"u,v"` edge strings, so rebuilding the interaction graph
        voids every result derived from the old one, while `model_id` still
        matches because it IS the same model.

        Deleting the session key is not enough on its own. Result geometry is
        drawn as raw Rhino objects onto the Results layers (`draw_results`,
        `draw_result_forces`), not through the scene, so the key alone would
        leave displaced blocks and force lines in the document with no data
        behind them — and `Session_clear` is the only other thing that would
        ever sweep them.

        Returns
        -------
        int
            The number of result sets deleted.

        """
        from compas_rhino.layers import delete_layers

        stored = self.get("results") or {}
        count = sum(len(sets) for sets in stored.values())

        layers = [self.results_layer(name) for name in stored]
        if layers:
            # Rhino refuses to delete the current layer, and the user has very
            # likely just been looking at a result.
            self._release_current_layer()
            delete_layers(layers)

        self.delete("results")
        # the record of what was on screen cannot outlive the results it names
        self.delete("shown_results")
        return count

    def draw_results(self, problem_name, results, model=None, key=None) -> int:
        """Draw the displaced geometry of a Results object under its problem.

        The displaced blocks go under "…::<problem>::Results::<key>::Displaced"
        and carry their transformation in User Text. Nothing is drawn by solving
        — only this call (Results_show) puts result geometry in the document.

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

        model = model or self.model
        if model is None or results is None:
            return 0

        # One sublayer per solved set ("RBE_BC1-BC2"), so several result sets
        # coexist under the problem instead of overwriting each other.
        layer = self.results_layer(problem_name, key, "Displaced" if key else None)
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
                    "result_key": key,
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

    def draw_result_forces(self, problem_name, results, model=None, key=None) -> int:
        """Draw the contact forces of a Results object under its problem.

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

        model = model or self.model
        if model is None or results is None:
            return 0

        layer = self.results_layer(problem_name, key, "Forces")
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

        # A resultant on a contact with a support block IS that support's
        # reaction, so it is drawn red rather than green — the two read very
        # differently and there is no other cue distinguishing them.
        supports = {block.graphnode for block in model.elements() if block.is_support}

        drawn = 0
        for point, vector, magnitude, edge in resultants:
            if magnitude <= 0:
                continue
            self._draw_contact_geometry(layer, results, edge)
            is_reaction = any(node in supports for node in edge)
            color = self.COLOR_REACTION if is_reaction else self.COLOR_FORCE
            guid = self._draw_centred_line(layer, point, [c * scale for c in vector], color=color)
            if guid is None:
                continue
            self.set_user_params(
                guid,
                {
                    "problem": problem_name,
                    "result_key": key,
                    "result_kind": "support_reaction" if is_reaction else "contact_resultant",
                    "edge": list(edge),
                    "resultant_global": list(vector),
                    "resultant_local": results.resultant_local(edge),
                    "force_magnitude": magnitude,
                },
            )
            drawn += 1

        rs.Redraw()
        return drawn

    def fade_model(self, amount=None) -> int:
        """Fade the model's blocks, so result geometry reads on top of them.

        This used to set a layer RENDER MATERIAL with a transparency. Render
        materials are only consulted by the display modes that render — stock
        Shaded paints its own neutral material — so the fade was invisible in
        the mode most people work in, which is exactly why it moved.

        A custom OBJECT colour is honoured by every display mode. Each block is
        given its own colour, blended from the colour it would have had toward
        white; `amount=0` puts the objects back on "colour by layer" rather than
        painting them a colour of their own.

        Rhino has no per-layer opacity, so "faded" is pale rather than
        see-through. Blocks are opaque either way — the old setting only ever
        looked transparent in Rendered mode.

        Parameters
        ----------
        amount : float, optional
            0.0 = restore, 1.0 = white. Defaults to
            `settings.blockmodel.results_model_transparency`.

        Returns
        -------
        int
            The number of block objects recoloured.

        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_dem.elements import Block

        if amount is None:
            amount = self.settings.blockmodel.results_model_transparency
        amount = min(max(float(amount), 0.0), 1.0)

        touched = 0
        for sceneobj in self.scene.find_all_by_itemtype(Block):
            base = self.COLOR_REACTION if sceneobj.item.is_support else self.COLOR_FADED_BLOCK
            for guid in sceneobj.guids:
                try:
                    if amount <= 0.0:
                        rs.ObjectColorSource(guid, 0)  # 0 = colour by layer
                    else:
                        rs.ObjectColor(guid, self._blend(base, (255, 255, 255), amount))
                    touched += 1
                except Exception:
                    continue  # a stale guid must not take the whole fade down

        rs.Redraw()
        return touched

    @staticmethod
    def _blend(color, target, amount) -> tuple:
        """Mix `color` toward `target` by `amount` (0 = color, 1 = target)."""
        return tuple(int(round(c + (t - c) * amount)) for c, t in zip(color, target))

    def _result_resultants(self, results) -> list:
        """[(point, vector, magnitude, edge), …] for every contact with a force.

        Lives in `compas_masonry.results`, which derives everything the reports
        show from a `Results` without Rhino — the drawing here and the reporting
        commands must agree on the numbers.
        """
        from compas_masonry.results import contact_resultants

        return contact_resultants(results)

    def set_object_color(self, guid, color) -> None:
        """Give one drawn object a custom object colour.

        Rhino objects default to "by layer"; assigning a colour switches the
        object to "by object", which every display mode honours. Failures are
        swallowed: a colour is cosmetic and must never take a draw down.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        if guid is None or color is None:
            return
        try:
            rs.ObjectColor(guid, tuple(color))
        except Exception:
            pass

    def _draw_contact_geometry(self, layer, results, edge):
        """Draw a contact by its class: polygon, line, or point.

        EdgeContact/VertexContact results carry no polygon, so filtering on
        face contacts alone would silently drop them (same trap as §1.7).
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
        self.set_object_color(guid, self.COLOR_CONTACT)
        self.set_user_params(guid, {"result_kind": "contact", "edge": list(edge)})
        return guid

    def _draw_centred_line(self, layer, point, vector, color=None):
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
        self.set_object_color(guid, color or self.COLOR_FORCE)
        return guid

    def _max_block_size(self, model=None) -> float:
        """Largest block bounding-box diagonal, the yardstick for force scaling."""
        from compas.geometry import bounding_box

        model = model or self.model
        largest = 0.0
        for block in model.elements():
            box = bounding_box(block.modelgeometry.vertices_attributes("xyz"))
            diagonal = sum((b - a) ** 2 for a, b in zip(box[0], box[6])) ** 0.5
            largest = max(largest, diagonal)
        return largest or 1.0

    # Everything a BC draws is either an applied load or a prescribed movement.
    # Anything not listed is a load.
    BC_DISPLACEMENT_KINDS = ("displacement", "rotation")

    def _bc_color(self, kind):
        """The object colour for a BC item: black for movement, green for load."""
        if kind in self.BC_DISPLACEMENT_KINDS:
            return self.COLOR_DISPLACEMENT
        return self.COLOR_FORCE

    def _draw_bc_vector(self, layer, kind, origin, vector, params=None):
        """Draw an arrow on a boundary condition layer and tag it."""
        import rhinoscriptsyntax as rs  # type: ignore

        end = [o + v for o, v in zip(origin, vector)]
        if end == list(origin):
            return None
        guid = rs.AddLine(origin, end)
        rs.CurveArrows(guid, 2)
        rs.ObjectLayer(guid, layer)
        self.set_object_color(guid, self._bc_color(kind))
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
        self.set_object_color(guid, self._bc_color(kind))
        tags = {"load_kind": kind}
        tags.update(params or {})
        self.set_user_params(guid, tags)
        return guid

    def _draw_rotation_circle(self, layer, origin, rotation, scale, kind="rotation", color=None):
        """Draw a rotation about an axis as a circle in the plane normal to it.

        Used for a prescribed `Rotation` (black) and for a `Moment` (green) — the
        geometry is the same, only the colour and the tag differ.
        """
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
        self.set_object_color(guid, color or self.COLOR_DISPLACEMENT)
        self.set_user_params(guid, {"load_kind": kind, "rotation": list(rotation), "applied_angle_rad": angle * scale})
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
