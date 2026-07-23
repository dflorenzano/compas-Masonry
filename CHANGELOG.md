# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

* Added `MasonrySession.set_model`, `MasonrySession.clear_model`, `MasonrySession.draw_model` as the shared install/clear/draw path for every model-creating command.
* Added `MasonrySession.redraw` to redraw the scene and keep Rhino guid tags in sync, since `Scene.redraw()` recreates every drawn object with new guids.
* Added `MasonrySession._tag_block_guids`, `MasonrySession.guid_element_map`, `MasonrySession.find_node` to resolve a Rhino object guid to its current graph node via a persistent `element_guid` Rhino User Text tag, robust to node renumbering and object renaming (replaces parsing the `"Block_N"` object name).
* Implemented `Add`/`Remove`/`Clear` support logic in `Model_supports.py`, syncing existing supports to the `Masonry::Model::Supports` layer on open.

### Changed

* `Model_blocks.py` now calls `session.clear_model()`/`session.set_model(model)` instead of duplicating scene setup/teardown inline.
* `Model_contacts.py` now calls `session.redraw()` instead of `session.scene.redraw()`, so Block guid tags survive.

### Removed

* Removed name-string parsing (`"Block_N"` → `int`) as the mechanism for resolving Rhino objects to graph nodes.


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
