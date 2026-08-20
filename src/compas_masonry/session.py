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

        # A new model is the point at which a leftover `blockmodel.json` from the
        # old key layout stops being harmless clutter and starts being wrong.
        self.purge_retired_keys()

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
    # That cost the MODEL being re-serialized on every problem edit — 0.45s for a
    # 6.5 MB BlockModel where the old `problems` key wrote kilobytes. The note here
    # used to say "if it bites, the fix is a dirty-flag on the analysis, not a
    # second key". That is what FOLDER_KEYS below is: the key stayed one, the
    # STORAGE became a directory, and `save_model` / `save_problems` each write only
    # their own half. It is still one key, so the binding guarantee is intact.
    #
    # `results` is still its own key. It shares the `analysis/` directory but not its
    # lifetime — see the note on FOLDER_KEYS.
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

    # Keys this plugin used to own. Their files are NOT removed by anything that
    # iterates SESSION_KEYS, so a session folder written before 2026-08-07 keeps a
    # `blockmodel.json` and a `problems.json` for ever — dead weight that `record()`
    # copies into every single snapshot (measured: 158 KB per record on a 50-block
    # arch), and a loaded gun besides: they hold a model in the PRE-revert
    # compas_dem shape, so any code still reading the old key finds a plausible
    # answer instead of nothing and draws the wrong model's contacts.
    RETIRED_KEYS = ["blockmodel", "problems"]

    def purge_retired_keys(self) -> list:
        """Delete the data files of keys the plugin no longer owns.

        Returns the names that were actually removed, so a caller can say so
        rather than deleting in silence.
        """
        removed = []
        for key in self.RETIRED_KEYS:
            path = self.datadir / f"{key}.json"
            if path.exists():
                path.unlink()
                removed.append(key)
        return removed

    # =============================================================================
    # Folder-backed storage
    # =============================================================================

    # Keys stored as a DIRECTORY of separate JSONs instead of one file.
    #
    # `LazyLoadSession` writes one `data/<key>.json` per key, so the whole model and
    # every problem were rewritten on any edit to anything inside them. On the test
    # arch the model is 29.4 KB of a 30.7 KB analysis and a problem is 682 bytes:
    # adding one load rewrote 30 KB to change under a kilobyte, and the note on
    # SESSION_KEYS records 0.45s per `set()` on a real 6.5 MB model.
    #
    # `analysis` deliberately stays ONE key. Splitting it back into `blockmodel` +
    # `problems` is what commit 791d87f undid: a Problem serializes as a guid
    # REFERENCE to its model, and `Analysis.__from_data__` is what rebinds them, so
    # two keys put that rebinding back in the hands of every load path. Only the
    # STORAGE is split.
    #
    # `analysis` and `results` are still two INDEPENDENT keys that merely share a
    # parent directory — `CM_TNA_envelope` deletes the analysis without deleting the
    # results, so each `delete` touches only the files its own key owns.
    FOLDER_KEYS = ("analysis", "results")

    @property
    def analysisdir(self):
        return self.datadir / "analysis"

    @property
    def problemsdir(self):
        return self.analysisdir / "problems"

    @property
    def resultsdir(self):
        return self.analysisdir / "results"

    @staticmethod
    def _safe_filename(name, taken) -> str:
        """A readable, filesystem-safe `<name>.json`, unique within `taken`.

        The filename is a HANDLE, never an identifier: nothing parses it back. The
        real name is in the manifest and inside the object, so mangling a character
        here costs nothing, and two problems called "a/b" and "a:b" collapsing to
        the same stem is resolved with a counter rather than by preserving them.
        """
        stem = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name)) or "unnamed"
        candidate = f"{stem}.json"
        index = 1
        while candidate in taken:
            candidate = f"{stem}_{index}.json"
            index += 1
        taken.add(candidate)
        return candidate

    def _drop_legacy_file(self, key) -> None:
        """Remove the pre-folder `data/<key>.json` once the folder supersedes it.

        It cannot be left behind: `record()` copies the whole data directory into
        every snapshot, and a later `undo()` would restore the stale monolith next
        to the folder.
        """
        (self.datadir / f"{key}.json").unlink(missing_ok=True)

    def _load_legacy(self, key):
        """Read the pre-folder `data/<key>.json`, or None.

        **This fallback is permanent, not a one-shot migration.** Every
        `__records/<id>/data/` snapshot taken before the folder existed holds a
        monolithic `analysis.json`, and `undo()` copies that directory back
        verbatim — so a legacy file can reappear in the working copy long after the
        session was first upgraded. The next `set()` converts it again.
        """
        import compas

        path = self.datadir / f"{key}.json"
        if not path.exists():
            return None
        return compas.json_load(path)

    def _dump_analysis(self, analysis, parts=None) -> None:
        """Write the analysis as `model.json` + one JSON per problem + a manifest.

        `parts=("model",)` writes ONLY the model, which is what `save_model` wants:
        its callers changed supports, materials or contacts and no problem. Passing
        None writes everything.

        The manifest is authoritative for the analysis name and for the problem
        ORDER. Problems are rewritten as a set rather than file by file, because a
        state with fewer problems than the last one would otherwise leave the extra
        files behind for a glob to find, resurrecting a problem that was deleted.

        Nothing here re-implements compas_dem: the parts come straight out of
        `analysis.__data__`, which is the same dict `compas.json_dump` would encode.
        """
        import shutil

        import compas

        data = analysis.__data__
        self.analysisdir.mkdir(parents=True, exist_ok=True)
        manifestfile = self.analysisdir / "_analysis.json"

        # A narrow write cannot be the first write: without the manifest, the load
        # path falls through to the legacy file and would read a stale model back
        # over the one just saved.
        if parts is not None and not manifestfile.exists():
            parts = None

        if parts is None or "model" in parts:
            modelfile = self.analysisdir / "model.json"
            if data["model"] is None:
                modelfile.unlink(missing_ok=True)
            else:
                compas.json_dump(data["model"], modelfile)

        if parts is None or "problems" in parts:
            shutil.rmtree(self.problemsdir, ignore_errors=True)
            self.problemsdir.mkdir(parents=True, exist_ok=True)

            taken = set()
            filenames = []
            for problem in data["problems"]:
                filename = self._safe_filename(problem.name, taken)
                compas.json_dump(problem, self.problemsdir / filename)
                filenames.append(filename)

            compas.json_dump({"name": data["name"], "problems": filenames}, manifestfile)

        self._drop_legacy_file("analysis")

    def _load_analysis(self):
        """Rebuild the Analysis from the folder, or fall back to the legacy file.

        The parts are handed to `Analysis.__from_data__`, so the model is rebound
        into every problem by compas_dem's own code — the property that keeping this
        as one key exists to preserve.
        """
        import compas
        from compas_dem.models import Analysis

        manifestfile = self.analysisdir / "_analysis.json"
        if not manifestfile.exists():
            return self._load_legacy("analysis")

        manifest = compas.json_load(manifestfile)
        modelfile = self.analysisdir / "model.json"

        return Analysis.__from_data__(
            {
                "name": manifest.get("name"),
                "model": compas.json_load(modelfile) if modelfile.exists() else None,
                "problems": [compas.json_load(self.problemsdir / f) for f in manifest.get("problems") or []],
            }
        )

    def _dump_results(self, stored) -> None:
        """Write `{problem: {key: Results}}` as one JSON per result set, plus a manifest.

        The manifest carries the true problem name and result key for each file, so
        the filename never has to be parsed back — which is what makes it safe to
        sanitize. It is written even when there is nothing stored, so that an empty
        `{}` reads back as `{}` rather than falling through to the legacy file.
        """
        import shutil

        import compas

        shutil.rmtree(self.resultsdir, ignore_errors=True)
        self.resultsdir.mkdir(parents=True, exist_ok=True)

        taken = set()
        manifest = []
        for problem_name, sets in (stored or {}).items():
            for result_key, results in (sets or {}).items():
                filename = self._safe_filename(f"{problem_name}__{result_key}", taken)
                compas.json_dump(results, self.resultsdir / filename)
                manifest.append([problem_name, result_key, filename])

        compas.json_dump(manifest, self.resultsdir / "_results.json")
        self._drop_legacy_file("results")

    def _load_results(self):
        """Rebuild `{problem: {key: Results}}` from the folder, or the legacy file."""
        import compas

        manifestfile = self.resultsdir / "_results.json"
        if not manifestfile.exists():
            return self._load_legacy("results")

        stored = {}
        for problem_name, result_key, filename in compas.json_load(manifestfile) or []:
            path = self.resultsdir / filename
            if path.exists():
                stored.setdefault(problem_name, {})[result_key] = compas.json_load(path)
        return stored

    def _dump_folder_key(self, key, value) -> None:
        if key == "analysis":
            self._dump_analysis(value)
        else:
            self._dump_results(value)

    # -- the four LazyLoadSession overrides ---------------------------------------
    #
    # Each one handles FOLDER_KEYS and delegates everything else to the parent. That
    # is why no command changed: every call site already goes through get / set /
    # delete / setdefault on these keys.

    def get(self, key, default=None, filepath=None):
        """As the parent, but reads FOLDER_KEYS from their directory."""
        if key in self.FOLDER_KEYS and filepath is None and key not in self.data:
            value = self._load_analysis() if key == "analysis" else self._load_results()
            # NOT cached when absent: `__contains__` distinguishes "stored as None"
            # from "not stored" by whether the key is in `data`, and an empty
            # results dict is a real value while a missing one is not.
            if value is None:
                return default
            self.data[key] = value
        return super().get(key, default, filepath)

    def set(self, key, value) -> None:
        """As the parent, but writes FOLDER_KEYS to their directory."""
        if key not in self.FOLDER_KEYS:
            return super().set(key, value)

        self.data[key] = value
        if value is None:
            # nothing to lay out; leaving the old folder would make the next read
            # resurrect what was just cleared
            return self.delete(key)
        if self.settings.autosync:
            self._dump_folder_key(key, value)

    def delete(self, key) -> None:
        """As the parent, but removes ONLY the files the given key owns.

        The two keys share the `analysis/` directory, so this cannot be an rmtree of
        the parent: `CM_TNA_envelope` deletes the analysis and keeps the results.
        """
        if key not in self.FOLDER_KEYS:
            return super().delete(key)

        import shutil

        self.data.pop(key, None)

        if key == "analysis":
            (self.analysisdir / "_analysis.json").unlink(missing_ok=True)
            (self.analysisdir / "model.json").unlink(missing_ok=True)
            shutil.rmtree(self.problemsdir, ignore_errors=True)
        else:
            shutil.rmtree(self.resultsdir, ignore_errors=True)

        self._drop_legacy_file(key)

    def dump(self, sessiondir=None) -> None:
        """As the parent, but never writes a FOLDER_KEY back as one file.

        `LazyLoadSession.dump` loops `self.data` and writes `datadir/<key>.json` for
        each, which would put the monolith back beside the folder. Only reachable
        with `autosync` OFF — `record()` empties `_data` around `super().record()`
        when it is on (see the note there), so the loop writes nothing then.
        """
        data = self._data
        held = {key: data[key] for key in self.FOLDER_KEYS if key in data}

        self._data = {key: value for key, value in data.items() if key not in self.FOLDER_KEYS}
        try:
            super().dump(sessiondir)
        finally:
            self._data = data

        for key, value in held.items():
            self._dump_folder_key(key, value)

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

        Writes ONLY `analysis/model.json`. Every caller — Model_contacts,
        Model_material, Model_materialassign, Model_supports — changes the model and
        no problem, and the model is the expensive part: 29.4 KB of a 30.7 KB
        analysis on the test arch, 6.5 MB on a real one.

        The name always said this; it used to call `save_analysis` anyway and rewrite
        every problem with it. Anything that changes a PROBLEM must still call
        `save_analysis`, which writes the whole folder.
        """
        if self.settings.autosync:
            self._dump_analysis(self.analysis, parts=("model",))

    def draw_model(self) -> None:
        """Draw the session BlockModel, honouring the BlockModel show settings.

        Blocks, supports, the interaction graph and the contact interfaces are
        each gated on their own `settings.blockmodel.show_*` flag. Those four
        flags existed since the settings dialog was written and were read by
        nothing until 2026-08-20 — the dialog offered them and the drawing
        ignored them.

        Gating at the ADD, not by hiding afterwards: an object that was never
        added has no guid to go stale, which is what `prune_stale_guids` spends
        its time on.
        """
        model = self.model
        if model is None:
            return

        settings = self.settings.blockmodel

        for block in model.elements():
            if not (settings.show_supports if block.is_support else settings.show_blocks):
                continue
            node = block.graphnode
            layer = "Masonry::Model::Supports" if block.is_support else "Masonry::Model::Blocks"
            self.scene.add(
                block,  # type: ignore
                name=f"Block_{node}",  # type: ignore
                group=f"Masonry::Model::Blocks::{node}",  # type: ignore
                layer=layer,  # type: ignore
            )

        if model.graph.number_of_edges() > 0:
            if settings.show_interactions:
                self.scene.add(model.graph, layer="Masonry::Model::Interactions")  # type: ignore
            if settings.show_contacts:
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
        self.save_problems()

    def remove_problem(self, name) -> bool:
        """Drop a problem from the analysis by name. True if one was removed."""
        for problem in list(self.analysis.problems):
            if problem.name == name:
                # `Analysis.problems` is a plain list attribute with no remove
                # method of its own.
                self.analysis.problems.remove(problem)
                self.save_problems()
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
        """Write the WHOLE analysis folder — model and every problem.

        Mutating a Problem or the model in place changes nothing on disk: the
        session is a cache in front of files and only a write call reaches them.

        Prefer the narrow pair when only one side changed — `save_model` for the
        model, `save_problems` for the problems. This is for the cases where both
        did, or where the caller cannot tell.
        """
        self["analysis"] = self.analysis

    def save_problems(self) -> None:
        """Persist in-place edits to the problems, WITHOUT rewriting the model.

        The counterpart to `save_model`, and the one that pays. A problem is
        kilobytes and the model is megabytes — 878 bytes against 0.50 MB on a
        200-block arch, which is 0.0001s against 0.031s to write, a factor of 300.
        Every problem edit used to pay the model write for nothing.

        Use it whenever the change is to a boundary condition, a solver, a contact
        law, or the set of problems itself. If the MODEL changed too, use
        `save_analysis`.
        """
        if self.settings.autosync:
            self._dump_analysis(self.analysis, parts=("problems",))

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
            # `boundary_conditions` is a LIST of BoundaryConditionGroups, so copy
            # each group rather than the list (list.copy() would share the groups,
            # and editing the duplicate would edit the original).
            problem._boundary_conditions = [group.copy() for group in source.boundary_conditions]
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
    COLOR_SELFWEIGHT = (100, 116, 139)  # per-block weight, the yardstick for the rest
    COLOR_NORMAL = (124, 58, 237)  # normal component of a contact resultant
    COLOR_FRICTION = (202, 138, 4)  # tangential (friction) component
    COLOR_DISPLACED = (255, 140, 0)  # displaced blocks, to read against the undisplaced model
    # Tensile corner forces. NOT COLOR_REACTION red, though red is the obvious
    # choice for "wrong": reactions are already red, and the two get drawn in the
    # same view. Magenta is the only warm colour left that is not one of them.
    COLOR_TENSION = (190, 24, 93)

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

    # `choose_boundary_condition` and `choose_boundary_conditions` lived here and
    # were deleted on 2026-08-07 with the move to BoundaryConditionGroup. They had
    # NO callers by then: both indexed the problem's flat list of conditions, which
    # is now a list of groups, and the two commands that remove things
    # (Problem_loads, Problem_displacements) build their own pick lists — they need
    # the (group, condition) pair to remove one, which a flat index cannot give.
    # `boundaryconditions.group_labels` / `bc_labels` are the label builders.

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

        from compas_masonry.boundaryconditions import group_names
        from compas_rhino.layers import delete_layers

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

    # `delete_bc_group_layer` and `delete_bc_layers` lived here and were deleted
    # on 2026-08-20 with zero callers between them. `prune_bc_group_layers`
    # covers the first (it removes every layer with no matching group, not just
    # one), and `delete_problem` covers the second by deleting the problem layer
    # that the BoundaryConditions subtree hangs off.

    def draw_problem_conditions(self, problem_name, model=None) -> None:
        """Clear and redraw every boundary condition of a problem.

        One Rhino layer per `BoundaryConditionGroup`, at
        "…::BoundaryConditions::<group name>" — the group IS the display grouping,
        so nothing session-side tracks which condition belongs where.

        Loads become arrows; a moment and a prescribed rotation become circles
        about their axis. No displaced copy of the geometry is drawn — that is
        what Results_show does.

        A load arrow is drawn so its HEAD lands on the point of application: the
        force pushes into the geometry instead of hanging off it. The two
        exceptions are the body force, which has no point of application to aim
        at, and a prescribed movement, which is the block travelling rather than
        something acting on it — both keep their tail on the point. See
        `_arrow_endpoints`.

        Dispatch is on the CLASS of each condition, with one exception: a moment
        is a `PointLoad` carrying a `moment` and a zero force (that is what
        `add_moment` builds), so `is_moment` is what separates the two.

        Supports are not drawn here at all: they are a model concern
        (`Block.is_support`) and are already drawn red on the model layer.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        from compas_masonry.boundaryconditions import components
        from compas_masonry.boundaryconditions import is_moment
        from compas_masonry.boundaryconditions import load_point
        from compas_masonry.boundaryconditions import loads_of

        problem = self.problems.get(problem_name)
        if problem is None:
            return

        model = model or self.model
        if model is None:
            return

        self.clear_bc_layers(problem_name)
        self.prune_bc_group_layers(problem_name)

        gravity_scale, load_scale, disp_scale = self._scales
        blocks = {block.graphnode: block for block in model.elements()}

        for group in problem.boundary_conditions:
            # An empty group draws nothing and gets no layer — `prune_bc_group_layers`
            # would remove it again anyway, and a layer that appears and vanishes as
            # a group fills up is worse than one that appears when there is something
            # in it.
            if not loads_of(group) and not group.displacements:
                continue
            layer = self.ensure_bc_sublayer(problem_name, group.name)

            for bc in loads_of(group):
                kind = type(bc).__name__

                # --- BodyForce: global, so drawn once at the world origin -----
                if kind == "BodyForce":
                    # the ONE load still drawn tail-first. It does not act at the
                    # spot it is drawn at — it acts on every block by its mass —
                    # so there is no point of application for a head to land on.
                    self._draw_bc_vector(
                        layer,
                        "body_force",
                        [0.0, 0.0, 0.0],
                        [a * gravity_scale for a in bc.acceleration],
                        {"acceleration": bc.acceleration, "loading_type": bc.loading_type},
                        at="tail",
                    )
                    continue

                block = blocks.get(bc.block_index)
                if block is None:
                    continue

                # --- Moment: a circle about its axis, like a rotation ---------
                if is_moment(bc):
                    self._draw_rotation_circle(
                        layer,
                        list(block.modelgeometry.centroid()),
                        [m * load_scale for m in bc.moment],
                        1.0,
                        kind="moment",
                        color=self.COLOR_FORCE,
                    )

                # --- PointLoad: at the point it was resolved to ---------------
                elif kind == "PointLoad":
                    origin = load_point(bc, block)
                    if origin is None:
                        continue
                    self._draw_bc_vector(
                        layer,
                        "point_load",
                        origin,
                        [f * load_scale for f in bc.force],
                        {"force": bc.force, "point": bc.point, "loading_type": bc.loading_type},
                    )

                # --- SurfaceLoad: the loaded face, plus a load arrow ----------
                elif kind == "SurfaceLoad":
                    params = {"load": bc.load, "face_index": bc.face_index, "loading_type": bc.loading_type}
                    # the face itself, so which face carries the load is visible —
                    # the arrow alone does not show that
                    self._draw_bc_face(layer, "surface_load_face", block, bc.face_index, params)
                    self._draw_bc_vector(
                        layer,
                        "surface_load",
                        list(block.modelgeometry.face_centroid(bc.face_index)),
                        [f * load_scale for f in bc.load],
                        params,
                    )

            for bc in group.displacements:
                block = blocks.get(bc.block_index)
                if block is None:
                    continue

                origin = list(block.modelgeometry.centroid())
                # unconstrained (None) components draw as 0.0, never written back
                vector = components(bc)
                if not any(vector):
                    continue

                if type(bc).__name__ == "Rotation":
                    self._draw_rotation_circle(layer, origin, vector, disp_scale)
                else:
                    # tail-first, unlike a load: this is the block TRAVELLING that
                    # way, not something pushing it, so the arrow leads away from
                    # where the block is now.
                    self._draw_bc_vector(
                        layer,
                        "displacement",
                        origin,
                        [v * disp_scale for v in vector],
                        {"translation": list(bc.translation)},
                        at="tail",
                    )

        rs.Redraw()

    def summary(self) -> str:
        """Everything the session holds, as text.

        Nothing in the plugin reported state: the model is on screen, but how
        many problems exist, what each carries, whether a solve is stored and
        where undo stands were only ever visible by running a command that
        happened to print them. Built as one string so the caller can print it,
        show it in an InfoForm, or both.

        Reads through the accessors rather than the raw keys, so a session that
        has never been written reports empty instead of raising.
        """
        from compas_masonry.boundaryconditions import conditions_of
        from compas_masonry.boundaryconditions import group_kind

        lines = []

        model = self.model
        if model is None:
            lines.append("analysis : no block model")
        else:
            lines.append(
                "analysis : elements {} | contacts {} | materials {}".format(
                    len(list(model.elements())),
                    len(list(model.contacts())) if model.graph else 0,
                    len(list(model.materials())),
                )
            )

        problems = self.problems
        active = self.active_problem_name
        if not problems:
            lines.append("problems : none")
        for name, problem in problems.items():
            solver = getattr(self.solver_of(problem), "name", None) or "no solver"
            lines.append(f"problem  : {name}{' (active)' if name == active else ''} - {solver}")
            groups = problem.boundary_conditions
            if not groups:
                lines.append("             no boundary conditions")
            for group in groups:
                lines.append(f"             [{group.name}] {group_kind(group) or 'empty'}: {len(conditions_of(group))}")

        stored = self.get("results") or {}
        if not stored:
            lines.append("results  : none")
        for name, sets in stored.items():
            lines.append(f"results  : {name} -> {', '.join(sorted(sets))}")

        for name, view in (self.get("shown_results") or {}).items():
            lines.append(f"on screen: {name} -> {view.get('mode')} {', '.join(view.get('keys', []))}")

        # plain attributes on the base session, not session data keys
        lines.append(f"history  : {len(self.history)} record(s), current {self.current}")
        if self.history and 0 <= self.current < len(self.history):
            # a record is (snapshot filepath, name) — [0] is a tempfile path
            lines.append(f"             at: {self.history[self.current][1]}")

        return "\n".join(lines)

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
            # its own colour, so the displaced copy reads against the model it
            # sits on top of — at a small displacement scale the two overlap
            # almost exactly, and in one colour the result looks like a no-op
            self.set_object_color(guid, self.COLOR_DISPLACED)
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
            The number of force objects drawn — resultants plus whatever the
            optional views added: per-block self-weight, and one line per contact
            corner when `show_cornerforces` is on.

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

        # Reaction values go on their OWN sublayer, so the numbers can be switched
        # off without losing the arrows. Only reactions are labelled: a dot per
        # contact resultant is one per contact and buries the model.
        tags_layer = self.results_layer(problem_name, key, "Forces::Values")
        create_layers_from_path(tags_layer, separator="::")
        clear_layer(tags_layer)

        settings = self.settings.blockmodel

        drawn = 0
        for point, vector, magnitude, edge in resultants:
            if magnitude <= 0:
                continue
            is_reaction = any(node in supports for node in edge)
            if not (settings.show_reactions if is_reaction else settings.show_resultants):
                # the decompositions and the corner forces below are still drawn:
                # normal, friction and per-corner are separate views, not extra
                # detail on the resultant
                self._draw_decomposition(layer, results, edge, point, scale, settings)
                drawn += self._draw_cornerforces(layer, results, edge, scale, settings, problem_name, key)
                continue

            self._draw_contact_geometry(layer, results, edge)
            color = self.COLOR_REACTION if is_reaction else self.COLOR_FORCE
            guid = self._draw_centred_line(layer, point, [c * scale for c in vector], color=color)
            if guid is None:
                continue
            self._draw_decomposition(layer, results, edge, point, scale, settings)
            drawn += self._draw_cornerforces(layer, results, edge, scale, settings, problem_name, key)
            if is_reaction:
                self._draw_value_tag(tags_layer, point, magnitude, edge, problem_name, key)
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

        drawn += self._draw_selfweight(problem_name, model, scale, settings, key)

        rs.Redraw()
        return drawn

    # `fade_model` and its `_blend` helper lived here and were deleted on
    # 2026-08-20 with the Fade/Keep prompt in Results_show. Fading the blocks
    # toward white was how result geometry was kept readable on top of them;
    # drawing the blocks as wireframe does that without repainting every block
    # object, so the fade, its `results_model_transparency` setting and
    # COLOR_FADED_BLOCK all went with it.

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

    def _draw_selfweight(self, problem_name, model, scale, settings, key=None):
        """Draw each block's self-weight as a downward force at its centroid.

        Self-weight is not a result — the solvers apply it unconditionally from
        block density and never report it back — but it is the force everything
        else is compared against, so it is drawn alongside the results and gated
        on `show_selfweight`.

        `scale` is the same relative factor the contact forces use, so a weight
        arrow and a resultant arrow of equal length mean equal newtons;
        `scale_selfweight` multiplies on top for when they differ by too much to
        read together.

        Mass comes from compas_dem's own `_element_mass`, which prefers a Block's
        `mass` and falls back to density x volume. Re-deriving it here would let
        the picture disagree with what the solver actually applied.
        """
        if not settings.show_selfweight:
            return 0


        from compas_dem.analysis.resolve import _element_mass
        from compas_rhino.layers import clear_layer
        from compas_rhino.layers import create_layers_from_path

        layer = self.results_layer(problem_name, key, "Selfweight")
        create_layers_from_path(layer, separator="::")
        clear_layer(layer)

        drawn = 0
        for block in model.elements():
            try:
                mass = _element_mass(block)
            except ValueError:
                # no material or no density: the solver would refuse this model
                # too, so say nothing here and let Problem_solve report it
                continue
            weight = mass * 9.81 * scale * settings.scale_selfweight
            guid = self._draw_centred_line(layer, list(block.modelgeometry.centroid()), [0.0, 0.0, -weight], color=self.COLOR_SELFWEIGHT)
            if guid is None:
                continue
            self.set_user_params(
                guid,
                {
                    "problem": problem_name,
                    "result_key": key,
                    "result_kind": "selfweight",
                    "element_guid": str(block.guid),
                    "mass": mass,
                    "force_magnitude": mass * 9.81,
                },
            )
            drawn += 1
        return drawn

    def _draw_decomposition(self, layer, results, edge, point, scale, settings):
        """Draw the normal and/or friction part of one contact resultant.

        `resultant_local` is the same force as `resultant_global`, expressed in
        the contact frame: z is the contact normal, x and y are the tangential
        directions. So the normal part is `local[2] * frame.zaxis` and the
        friction part is `local[0] * frame.xaxis + local[1] * frame.yaxis`, and
        the two sum back to the resultant. Nothing new is computed here — this
        is the stored answer, split.

        Both are off by default: drawing a resultant together with both of its
        parts puts three lines through one contact point.
        """
        if not (settings.show_normalforces or settings.show_frictionforces):
            return

        local = results.resultant_local(edge)
        frame = results.contact_frame(edge)
        if local is None or frame is None:
            return

        if settings.show_normalforces:
            normal = [c * local[2] * scale for c in frame.zaxis]
            self._draw_centred_line(layer, point, normal, color=self.COLOR_NORMAL)

        if settings.show_frictionforces:
            friction = [(x * local[0] + y * local[1]) * scale for x, y in zip(frame.xaxis, frame.yaxis)]
            self._draw_centred_line(layer, point, friction, color=self.COLOR_FRICTION)

    def _draw_cornerforces(self, layer, results, edge, scale, settings, problem_name=None, key=None):
        """Draw the per-corner normal forces of one contact.

        A solver does not solve for the resultant — it solves for a force at every
        vertex of the contact polygon, and the resultant is their sum. This draws
        what was solved: one line per corner, along the contact normal, centred on
        the corner so the direction reads without an arrowhead.

        Why it matters beyond detail: a contact whose RESULTANT is compressive can
        still have tensile corners, which is exactly what a CRA penalty solve
        permits and the plain formulation forbids. The resultant hides that; this
        is the only view that shows where the tension actually is. Compression is
        drawn in the normal-force colour and tension in `COLOR_TENSION`.

        `FrictionContact.compressiondata` / `.tensiondata` already return
        `[x, y, z, nx, ny, nz, 0.5 * force]` per corner — point, normal axis, half
        magnitude — so nothing is recomputed here. Note the halving: the data is
        built for a line spanning ±half, and `_draw_centred_line` halves again, so
        the magnitude is doubled back before it is passed on.

        Not every contact is a `FrictionContact`. LMGC90 stores an `EdgeContact` or
        a `VertexContact` for degenerate contacts, and those carry no per-corner
        forces at all — hence `getattr` rather than an attribute access.

        Returns
        -------
        int
            The number of corner forces drawn.

        """
        if not settings.show_cornerforces:
            return 0

        contact = results.contact_data(edge)
        if contact is None:
            return 0

        drawn = 0
        for attr, color, kind in (
            ("compressiondata", self.COLOR_NORMAL, "corner_compression"),
            ("tensiondata", self.COLOR_TENSION, "corner_tension"),
        ):
            for entry in getattr(contact, attr, None) or []:
                point = entry[:3]
                axis = entry[3:6]
                magnitude = entry[6] * 2.0
                guid = self._draw_centred_line(layer, point, [c * magnitude * scale for c in axis], color=color)
                if guid is None:
                    continue
                self.set_user_params(
                    guid,
                    {
                        "problem": problem_name,
                        "result_key": key,
                        "result_kind": kind,
                        "edge": list(edge),
                        "force_magnitude": abs(magnitude),
                    },
                )
                drawn += 1

        return drawn

    def _draw_value_tag(self, layer, point, magnitude, edge, problem_name=None, key=None):
        """Label a resultant with its magnitude, as a TextDot at its contact point.

        A TextDot rather than text geometry: it keeps one screen size whatever
        the zoom and stays readable from any view direction, which text in the
        model plane does not. `%.4g` matches Results_print, so the number on
        screen is the number in the report.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        guid = rs.AddTextDot(f"{magnitude:.4g}", list(point))
        if guid is None:
            return None
        rs.ObjectLayer(guid, layer)
        self.set_object_color(guid, self.COLOR_REACTION)
        self.set_user_params(
            guid,
            {
                "problem": problem_name,
                "result_key": key,
                "result_kind": "reaction_value",
                "edge": list(edge),
                "force_magnitude": magnitude,
            },
        )
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

    @staticmethod
    def _arrow_endpoints(origin, vector, at):
        """Start and end of a BC arrow. `rs.CurveArrows(guid, 2)` heads the END.

        `at` says where the point of application sits on the arrow:

        - "tip"  — the head lands ON the point, so the vector PUSHES into the
          geometry. This is what a force does, and drawing it the other way
          reads as the load hanging off the block rather than acting on it.
        - "tail" — the arrow starts at the point and leads away from it. Right
          for a body force, which acts on the whole model rather than at the
          spot it is drawn at, and for a prescribed movement, which is the
          block travelling in that direction rather than something pushing it.

        """
        if at == "tip":
            return [o - v for o, v in zip(origin, vector)], list(origin)
        return list(origin), [o + v for o, v in zip(origin, vector)]

    def _draw_bc_vector(self, layer, kind, origin, vector, params=None, at="tip"):
        """Draw an arrow on a boundary condition layer and tag it."""
        import rhinoscriptsyntax as rs  # type: ignore

        start, end = self._arrow_endpoints(origin, vector, at)
        if start == end:
            return None
        guid = rs.AddLine(start, end)
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
    # Rhino User Text (a str -> str dict per object): params out
    # =============================================================================
    #
    # Write only. `get_user_params`, the symmetric reader, was deleted on
    # 2026-08-20 with no callers: the two places that read User Text
    # (`find_node`, `find_material`) want ONE known key and call
    # `rs.GetUserText(guid, key)` directly, which needs no JSON decoding and no
    # helper. The tags written here are for the user to read in Rhino's
    # properties panel, not for the plugin to read back.

    def set_user_params(self, guid, params: dict) -> None:
        """Write a dict of parameters onto a Rhino object's User Text.

        User Text only stores strings, so non-string values are JSON-encoded and
        strings are stored raw (keeps identifier tags like "element_guid"
        readable and back-compatible with find_node/find_material). A ``None``
        value deletes that key.

        **COMPAS geometry is encoded as a plain list, not as a `dtype` dict.**
        `default=list` catches anything `json` cannot take but that iterates like
        a sequence — `Point`, `Vector`, and by recursion a `Polygon`'s points.
        That matters because compas_dem hands back both shapes for the same
        quantity: `Problem.add_point_load_at_vertex` resolves its anchor with
        `vertex_coordinates()`, which returns a **list**, while
        `add_point_load_at_face` uses `face_center()`, which returns a **Point**.
        Tagging a face-anchored load used to die with
        `TypeError: Object of type Point is not JSON serializable` — and because
        `draw_problem_conditions` tags as it draws, one such load aborted the
        whole redraw, leaving the arrows of the loads before it on screen and none
        after. The load itself was always added and saved; only the picture was
        missing, which read as "it only applied to one block".

        `compas.json_dumps` would also encode these, but as `{"dtype": …}`
        wrappers, and every reader here does a plain `json.loads` and expects
        `[x, y, z]`. A type that is neither JSON-native nor iterable still raises,
        which is what should happen.
        """
        import json

        import rhinoscriptsyntax as rs  # type: ignore

        for key, value in params.items():
            if value is None:
                rs.SetUserText(guid, key, None)
            elif isinstance(value, str):
                rs.SetUserText(guid, key, value)
            else:
                rs.SetUserText(guid, key, json.dumps(value, default=list))
