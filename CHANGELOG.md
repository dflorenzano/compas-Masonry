# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added — 2026-07-30 (a simulation runs end to end)

* A simulation now runs end to end in Rhino with **CRA or RBE**: model → contacts → supports → material → problem → contact law → solver → boundary condition → solve → results. Verified in Rhino and headless on Rhino's own python3.9.
* Added `MasonrySession.draw_result_forces`, which draws contact resultants and contact geometry under `…::Results::<key>::Forces`. CRA and RBE store an *identity* transformation per block and put the whole answer on the contact edges, so a displaced-geometry view of their results showed a duplicate of the model and looked like nothing had happened. Force lines are centred on the contact point, contacts are drawn by class (face → polygon, edge → line, point → point), and each carries its magnitudes as User Text.
* Added `settings.blockmodel.scale_forces`, a **dimensionless** result-force scale: at 1.0 the largest resultant in a result set is drawn half as long as the biggest block is wide, so forces are visible without per-model tuning whatever the units are.
* Added `MasonrySession.ensure_solver_path` and `settings.solver_bin`. compas_cra resolves `ipopt` as an *executable* on `PATH`, and Rhino launched from the Finder has no shell `PATH`, so a conda-installed ipopt was invisible and the solve died inside pyomo saying nothing about `PATH`.
* Added `MasonrySession.clear_all`, so `Session_clear` empties the document: the whole `Masonry` layer tree (children included, which also sweeps orphans from an earlier crash) plus every session key the plugin owns.
* Added `MasonrySession.refresh_problem_supports` and a `RefreshSupports` operation to `Problem_create`. Supports are copied onto a problem at creation and into each boundary condition at registration, so editing them afterwards silently left every problem holding the old set. `Model_supports` now detects that and offers to refresh. Prescribed displacements are preserved.
* Added **BC kinds** — `Gravity | Loads | Displacements | Mixed` — chosen with the name in `Problem_createbc` and enforced by `Problem_addload` and `Problem_displacements`. Held session-side (`session.bc_kinds`), keyed by index and reindexed when a BC is deleted, since compas_dem's `BoundaryCondition` has no such field.
* Added a **BodyForce** load type: an acceleration applied to every block by its mass, expanded into one centroid point load each (`mass * a * direction̂`). This is the tilted-table / static-seismic load, expressed so that every solver reading point loads honours it without a compas_dem change.
* Added `units=` to `compas_masonry.inputs`, shown as a legend of the currently visible fields on the command line and appended to the label in the Eto renderer. A Rhino option renders as `Keyword=Value` and nothing else, so units written into `prompt` were invisible until the option was picked.
* Added `settings.blockmodel.results_model_transparency` and `MasonrySession.set_model_transparency`, to fade the blocks while results are drawn on top. Transparency lives in a layer's render material, so it only shows in Rendered/Raytraced display modes.
* Added `tests/rhinostub.py` and `tests/test_command_helpers.py` — 35 headless tests covering face parsing, the BC-kind matrix and its reindexing, result keys, BC naming, body forces and the supports refresh. `compas_masonry.inputs` touches `Rhino.Input.Custom` at class-definition time, which had made every command module unimportable outside Rhino.

* Added `compas_masonry.results`, which derives everything a report or a drawing needs from a `Results` — contact resultants, face stresses, joint openings, per-body displacements, support reactions, and a tagged summary of the maxima — with no Rhino, so the reporting commands and the force drawing cannot disagree and both are testable headlessly.
* Implemented the three Results stubs on top of it: `Results_print` (Summary / Contacts / Blocks / Reactions), `Results_blockdata` (per selected block, printed or written back as User Text), and `Results_export` (Json round-trip of the Results, or Csv per contact).

### Changed — 2026-07-30

* **`LoadCase` → `BoundaryCondition`**, following the compas_dem rename (`a6454c6`, no compatibility alias): `compas_masonry/loadcases.py` → `boundaryconditions.py` (`bc_name`, `bc_labels`), the session's layer API (`bc_layer`, `ensure_/clear_/delete_bc_layers`, `choose_bc(s)`, `draw_bc`, `draw_problem_bcs`), and the layer prefix `LC<n>_` → `BC<n>_`. `CM_Problem_createloadcase.py` → `CM_Problem_createbc.py`, and `CM_Problem_boundaryconditions.py` → `CM_Problem_displacements.py`, whose old name now collided with the BC concept. Existing session JSON holding `LoadCase` dtypes no longer loads.
* Solving no longer offers PerLoadCase/Combined: **every selected BC solves together**, in list order, and the result is stored under a key naming the solver and the BCs (`RBE_BC1-BC2`). An identical key is reused rather than re-solved. There is no stepped solve.
* `Problem_solve` checks contacts, solver, contact law, supports and material densities before starting, and resolves `ipopt` first, so a failure names the command to run instead of surfacing a traceback.
* `Results_show` draws per stored result set, with a Forces / Displaced / Both mode that defaults to **Forces** when every transformation is an identity.
* The solver picker is now CRA / RBE / LMGC90 (PRD and BLA dropped), with LMGC90 guarded by an importability probe. `d_bnd`/`eps`, `mu` and `theta` are deliberately not exposed — see `REFACTOR_GUIDE.md` §6.
* BC sublayers are created **only when they have content**, so a gravity-only BC grows no `Displacements` layer and `Results` appears only once results are drawn.
* Surface loads accept **several faces** (`0,3,5` or `all`), one entry per face; invalid entries are reported rather than silently loading the wrong face.
* A new BC no longer arrives carrying a gravity load: `BoundaryCondition` is constructed with `g=9.81`, so only a Gravity or Mixed BC keeps it. (`bc.g` is a flag — CRA and RBE apply self-weight internally regardless.)
* `Problem_contactlaw` prints **both** phi and mu, read back from the stored contact model, since they are two views of the same thing and mu is what the solvers use.
* `Model_materialassign` now tags blocks with `material_name` as well as `material_guid`.
* `fc` → `fck` in `Model_material`, following compas_dem `c924950`; `Ecm` is labelled MPa (the predefined values are 20000/30000).

### Fixed — 2026-07-30
* `contact_frame` is absent from every CRA/RBE result — `_post_processing_cra` writes the polygon, points, resultants and magnitude and nothing else — so deriving the contact normal from the frame silently returned **no stress and no reactions** for them. The normal now falls back to the contact polygon's own normal; pinned by `tests/test_results.py`.

* `MasonrySession.clear_model` deleted the session key `"problem"`, but the key the plugin writes is **`"problems"`** — so stale problems and `active_problem` survived a model swap, pointing at a deleted model.
* `bc_name` returned `"BoundaryCondition"` for an unnamed BC, making the `BC<n>` fallback unreachable: compas's `Data.name` returns `self._name or self.__class__.__name__`. It now reads `_name`.
* `create_problem`'s duplicate path called `source.boundary_conditions.copy()`, which since the rename copies a *list* and shares the BC objects between problems. Each BC is now deep-copied.
* `session.draw_problem` (shared with the frozen original commands) assumed `problem.boundary_conditions` was a single object; it is now a list.
* `print_predefined` in `Model_material` still read the `fc` key and would have printed "-" for every material's strength.
* Fixed two pre-existing test failures from upstream API drift: `problem.contact_properties` became a property, and `Mesh.volume` a method.

* Registered all 33 commands in `COMPAS-Masonry.rhproj` and `resources/rui/ui.json`, and rebuilt the toolbars in workflow order. `Problem_solve` sits at the end of the **Problem** toolbar, not in Results: solving is the last step of setting a problem up, and Results holds what you do with the answer. Renamed entries in place so each keeps its `id` and icon; the four genuinely new commands (`Problem_createbc`, `Results_show`, `Masonry_export`, `Masonry_import`) borrow a sibling's icon.
* Fixed the toolbars pointing at commands that do not exist: the items still used un-prefixed names (`Masonry_Start`) after the `CM_` rename, so every button silently did nothing — the RUI loads fine either way.
* Removed five stale registry entries whose command files are gone (`Session_settings`, `Problem_loads`, `Problem_boundaryconditions`, `Problem_contactmodel`, `Solve`) by pointing them at the commands that replaced them.

* Brought every working doc in line with the code: `REFACTOR_GUIDE.md` gained §1.5 on the two ways to run a command and what a build actually changes, `IMPLEMENTATION_PLAN.md`'s next actions are now the build-and-release list, and `ARCHITECTURE_STUDY.md` / `RHINO_PRIMER.md` / `RHINO_DEV_GUIDE.md` no longer describe load cases, two command sets, or an unregistered `_options` set.
* Rewrote the user-facing `README.md`: all 33 commands by group (checked against the registry), a Solvers section stating that CRA/RBE work and need the unreleased compas_cra 0.5.0 plus pyomo >= 6.7.3, and that LMGC90 has no Rhino build. It had claimed the plugin shipped no solvers at all, and told users to "install RhinoVAULT with Yak".
* Extended `tests/rhino/README.md` with the whole-workflow manual checks and the after-a-build checks.

* Fixed `CM_Problem_addload` throwing `NameError: name 'bc_name' is not defined` partway through the command — it used the helper without importing it. A command body only runs inside Rhino, so this survived every headless test and `compileall`. `tests/test_lint.py` now runs ruff F821/F811 over `commands/`, `src/` and `tests/`, which catches the whole class statically.

### Environment — 2026-07-30

* CRA/RBE could not run in the Rhino site-env at all: it ships **numpy 2.0.2**, and **pyomo 6.4.2** registers `np.float_` (removed in NumPy 2) at import. Patching the alias makes the import succeed and then produces a corrupt `.nl` file (`np.float64(-0.0)` → ipopt `INVALID_TNLP`), so it is not a fix. pyomo ≥ 6.7.3 in turn breaks **compas_cra 0.4.0** (`MatrixConstraint`), and PyPI has nothing newer. Resolved with **pyomo 6.8.2 + the local compas_cra 0.5.0 fork** (`--no-deps --ignore-requires-python`), installed into the site-env. Full account in `temp/COMMANDS_REVIEW.md` §12.
* A stale `build/` tree makes setuptools package deleted modules, so a renamed file keeps reappearing in the site-env after every sync. `rm -rf build/` after any rename.

### Added

* Added `compas_masonry.inputs`: command line input built on `Rhino.Input.Custom.GetOption`, so a command shows every parameter at once instead of a chain of sequential `rs.GetString`/`rs.GetReal` prompts. `Options` (with `add_number`/`add_integer`/`add_toggle`/`add_list`/`add_text` and a `visible` predicate for dependent fields), `choose`, and the `BACK` sentinel for a "Back" option that steps to the previous window. COMPAS has no parameter-input layer for Rhino — `compas_rhino` covers object selection and file browsing only — which is what this fills.
* Added `Options.from_model` / `Options.apply`, which build the options from a pydantic model's fields (title, default, `ge`/`le`), so one settings model renders either as the Eto `SettingsForm` or on the command line. `field_ge`/`field_le` moved to `compas_masonry.inputs` and are re-exported from `compas_masonry.forms.settings`.
* Added a `keywords` mode to `MasonrySession.choose_problem`: problem names are offered as command line options with the active problem as the Enter default, instead of picking a printed index.
* Added `compas_masonry.loadcases`, the single bridge to the incoming compas_dem LoadCase API (`LoadCase`, `Problem.add_loadcase`, `BlockModel.solve(problem=, loadcases=)`). Commands are written against that API already; until it lands the helpers raise `LoadCaseUnavailable` with an explanatory message instead of an ImportError traceback.
* Added the load case layer hierarchy to `MasonrySession`: `indexed_problem_layer`, `renumber_problem_layers`, `loadcase_layer`, `ensure_loadcase_layers`, `clear_loadcase_layers`, `delete_loadcase_layers`, `delete_all_loadcase_layers`, `choose_loadcase`, `choose_loadcases`, `draw_loadcase`, `draw_problem_loadcases`, `draw_results`.
* Added `commands/*_options.py`, the RhinoCommon variant of every command that takes input, plus the new commands of the dev notes refactor: `Problem_createloadcase`, `Problem_addload`, `Problem_solve`, `Results_show`, `Masonry_export`, `Masonry_import`.
* Added a temporary face-index helper to `Problem_addload`: the faces of the selected block are labelled with their index while the surface load face is picked, and the labels are always removed afterwards.
* Added a session-level export/import pair (`Masonry_export` / `Masonry_import`) covering the model, every problem with its load cases, the active problem and the display settings in one JSON file.
* Added `compas_masonry.forms.options.OptionsForm`, an Eto renderer for the same `Options` declaration the command line uses. `Options.get()` dispatches on the new `settings.dialog_input` (Session_settings -> Input), so no command has to know which renderer is running; the form writes back into the same Rhino option objects, leaving `Options.values` identical either way. Useful on macOS, where Rhino's command options dialog always carries an empty text entry box that no `GetOption` API can remove.
* Added `temp/REFACTOR_GUIDE.md`, a full walkthrough of the refactor: how to get the repo running (sync scripts, engine reload, build), the data model and layer tree, every command, the backend modules, and the known gaps.

* Added `MasonrySession.set_model`, `MasonrySession.clear_model`, `MasonrySession.draw_model` as the shared install/clear/draw path for every model-creating command.
* Added `MasonrySession.redraw` to redraw the scene and keep Rhino guid tags in sync, since `Scene.redraw()` recreates every drawn object with new guids.
* Added `MasonrySession._tag_block_guids`, `MasonrySession.guid_element_map`, `MasonrySession.find_node` to resolve a Rhino object guid to its current graph node via a persistent `element_guid` Rhino User Text tag, robust to node renumbering and object renaming (replaces parsing the `"Block_N"` object name).
* Implemented `Add`/`Remove`/`Clear` support logic in `Model_supports.py`, syncing existing supports to the `Masonry::Model::Supports` layer on open.

### Changed

* Every file in `commands/` is now prefixed `CM_` (`Model_blocks.py` → `CM_Model_blocks.py`), so command files are recognizable at a glance. The filename **is** the Rhino command name, so the commands are now `CM_Model_blocks`, `CM_Problem_create`, and so on; `COMPAS-Masonry.rhproj` (`title` + `uri`) and `resources/rui/ui.json` (`name` + `! _<macro>`) were updated to match — 28 entries each. `commands/old/` was left alone.
* Load cases, not problems, now own the loads, the boundary conditions and the results (dev notes). A problem gets one layer, `Masonry::<index>_<name>`, with no Loads/Boundary conditions sublayers; each load case creates its own subtree on demand, `…::LC<n>_<name>::Loads|Displacements|Results`. Deleting a problem renumbers the remaining problem layers. `MasonrySession.create_problem` takes `sublayers=False` for the new hierarchy and `delete_problem` takes `indexed=True`; the defaults keep the pre-loadcase commands working unchanged.
* `Problem_create` asks for the problem name as a named option seeded with the next free `Problem_<n>` (no string prompt on the first window), and gained a `Delete` operation, which is where the layer renumbering happens.
* `Problem_boundaryconditions` now edits a load case, and draws a prescribed displacement as an arrow and a prescribed rotation as a circle around its axis — no displaced copy of the geometry (that is `Results_show`).
* `Model_material` prints every predefined material with its values as a table before the pick, offers a `Custom` entry in the same list that leads into the custom generation, and offers `Back` on the property window.
* `Problem_solve` draws nothing: it stores one result per solved load case on the session, and `Results_show` is what puts displaced geometry in the document.
* Restyled the splash screen (`resources/splash/`): light layout matched to the artwork with its coral as the only accent, a white scrim for legibility, real Yes/No buttons and hover states.
* Deduplicated the command helpers against upstream: list dialogs use `rs.ListBox`, yes/no uses `compas_rui.feedback.confirm`, problem picking uses `MasonrySession.choose_problem` — replacing the `pick_from_list`, `confirm` and `choose_problem` helpers that had been added to `compas_masonry.inputs`.
* `Model_blocks.py` now calls `session.clear_model()`/`session.set_model(model)` instead of duplicating scene setup/teardown inline.
* `Model_contacts.py` now calls `session.redraw()` instead of `session.scene.redraw()`, so Block guid tags survive.

### Fixed

* `MasonrySession.redraw` no longer dies with `AttributeError: 'NoneType' object has no attribute 'RuntimeSerialNumber'`. `Scene.redraw()` purges every guid its scene objects still hold, and `compas_rhino.objects.purge_objects` dereferences `find_object(guid)` without a None check — so one scene object holding a guid whose Rhino object is gone breaks the redraw of the whole scene. The new `MasonrySession.prune_stale_guids()` drops those guids first, and runs on every `session.redraw()`. A guid is dropped only when the lookup `purge_objects` uses reports it gone, so the redraw keeps deleting everything it should.
* Fixed the **duplicate geometry** that followed such a crash: two copies of every block. `Scene.clear()` nulls each scene object's `_guids` *before* purging them, so a crash mid-purge left the scene tracking nothing while every Rhino object stayed in the document — orphans invisible to all later redraws, with the next draw stacking a fresh set on top. Preventing the crash prevents the orphans; orphans already saved in a `.3dm` are swept by the next `clear_model()`.
* `MasonrySession.clear_model` now prunes stale guids first, clears each scene object (`obj.clear()`) before removing it, and matches `EdgeContact` / `VertexContact` alongside `FrictionContact` — the same three corrections applied to `Model_contacts`, so every teardown path behaves the same way.
* `Model_contacts` now clears contact/graph scene objects (`obj.clear()`) before removing them, and matches `EdgeContact` and `VertexContact` as well as `FrictionContact`. Those two are plain `Data` subclasses, **not** `FrictionContact` subclasses, so `find_all_by_itemtype(FrictionContact)` left their scene objects behind while `clear_layer` deleted the geometry under them — the exact way the redraw above got poisoned. The same pattern is still present in the frozen original `CM_Model_contacts.py`, which is now protected by the session-level prune rather than fixed in place.
* `session.draw_loadcase` now redraws the loaded face of a surface load, not only the load arrow — the face mesh was drawn by the old `draw_problem` and was lost in the load case rewrite.
* `compas_masonry.forms.settings.SettingsForm` no longer raises `TypeError` on non-class field annotations (`Optional[...]`, `Literal[...]`, `list[...]`): the `issubclass(field.annotation, BaseModel)` check is guarded with `isinstance(field.annotation, type)`.

### Removed

* Removed `Problem_contactmodel`, renamed to `Problem_contactlaw` (dev notes: a problem holds one solver and one contact law).
* Removed `Problem_loads`, superseded by `Problem_addload` (loads belong to a load case).
* Removed `pick_from_list` and `confirm` from `compas_masonry.inputs`, and the module-level `choose_problem` that forked `MasonrySession.choose_problem`.
* Removed name-string parsing (`"Block_N"` → `int`) as the mechanism for resolving Rhino objects to graph nodes.

### Adapted to the shipped compas_dem LoadCase API

The `LoadCase` / `Results` API landed in compas_dem, and differs from the dev notes in ways that changed the commands:

* `LoadCase.add_point_load(block_index=, force=, moment=, point=, loading_type=)` and `add_surface_load(block_index=, face_index=, load=, loading_type=)` — not the `add_pointload(block_idx=, forcevector=)` spelling of the notes. The commands call them directly and expose `loading_type` (ramp / instantaneous) as an option.
* `LoadCase.add_displacement(block_index, dx=, dy=, dz=)` is **per component**, where `None` means the DOF is unconstrained — which is not the same as prescribing 0.0. `Problem_boundaryconditions` mirrors that with a Prescribed/Free toggle per axis, and the value option for an axis only appears when that axis is constrained.
* `Problem.add_loadcase` returns the index to use and *replaces* the auto-created "default" load case at index 0 when one exists, so the return value is used rather than `len(loadcases) - 1`. Supports live on the Problem and are copied into each load case as it is registered.
* `BlockModel.solve(problem, loadcases=[...])` returns ONE `Results` for the whole call and solves the given load cases concurrently — not one result per load case. `Problem_solve` exposes the resulting choice: `PerLoadCase` (default, one solve each, matching the per-load-case Results layers) or `Combined` (one concurrent solve, stored under the first selected load case).
* `Results` is a compas Data, so it serializes onto the session as is, and `Results.displacement_scale` does the exaggeration inside `Results.transformation`. `session.draw_results` sets it from `settings.blockmodel.scale_displacement`.
* `Solver` now offers LMGC90 / CRA / PRD / **BLA** / RBE (no DPRD). `Problem_solver` follows, with the real parameters per solver; the dict-shaped `non_linear_params` / `non_associative_params` are left at their compas_dem defaults since they have no command line widget.
* `compas_masonry.loadcases` shrank from an availability/compat shim to display helpers only (`loadcase_name`, `loadcase_labels`, `is_support`, `entry_vector`, `describe_entry`); commands import `LoadCase` from `compas_dem.problem` directly.

### Known gaps

* Every command file is now prefixed `CM_` (see below), which renames the Rhino commands themselves.
* Nothing in the `*_options` set has been exercised inside Rhino yet.
* The `*_options` commands are not registered in `COMPAS-Masonry.rhproj` / `resources/rui/ui.json` — they run from the script editor only.


## [0.3.0] 2025-09-10

### Added

* Added `compas_masonry.viewer.MasonryViewer` for interactive visualization of masonry structures.

### Changed

### Removed


## [0.2.7] 2025-09-10

### Added

### Changed

### Removed


## [0.2.6] 2025-09-10

### Added

### Changed

### Removed


## [0.2.5] 2025-09-09

### Added

### Changed

### Removed


## [0.2.4] 2025-09-09

### Added

* Updated TNA_Loads and TNA_analysis

### Changed

### Removed

## [0.2.3] 2025-09-09

### Added

* Added MeshEnvelope options to TNA_Envelope

### Changed

### Removed


## [0.2.2] 2025-09-09

### Added

### Changed

### Removed


## [0.2.1] 2025-09-09

### Added

### Changed

### Removed


## [0.2.0] 2025-09-08

### Added

### Changed

### Removed


## [0.1.1] 2025-09-07

### Added

### Changed

### Removed
