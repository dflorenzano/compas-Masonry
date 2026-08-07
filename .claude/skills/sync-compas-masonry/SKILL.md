---
name: sync-compas-masonry
description: >
  Sync local edits to THIS plugin's package (src/compas_masonry/...) into
  Rhino's RhinoCode site-env so the script editor picks them up. Use when you
  edited the plugin's Python package — e.g. src/compas_masonry/session.py,
  scene/, forms/, settings.py — and Rhino doesn't see the change (a command
  calls a helper that "doesn't exist", or a Rhino traceback points at
  .rhinocode/py39-rh8/site-envs/.../compas_masonry/... that doesn't match the
  local repo). This is the plugin-package twin of sync-compas-dem. Trigger
  phrases: "sync compas_masonry", "sync the plugin", "update compas_masonry in
  rhino", "push my plugin changes to rhino", "reinstall compas_masonry".
  NOTE: files under commands/ are never synced — the Script Editor reads them
  live from the repo, and the installed plugin carries its own embedded snapshot
  that only a rebuild replaces. This skill covers src/compas_masonry only.
---

# Sync compas-Masonry plugin into Rhino

## Why this exists

The Rhino site-env at `~/.rhinocode/py39-rh8/site-envs/brg-csd-*/` contains a
flat `pip install --target` dump of `compas_masonry` (see the
`compas_masonry-<version>.dist-info` folder next to the package). It is **not**
an editable install. Editing `~/Code/Libs/compas-Masonry/src/compas_masonry/...`
never touches it — the `# r: compas_masonry>=...` header on each command imports
the old installed copy until it's manually reinstalled.

**Key distinction from command files:** the `commands/*.py` files never need
syncing — but "always live" is only true of the Script Editor, which runs them
straight from the repo path. The **installed plugin** embeds its own compressed
copy of them (unpack the `.yak`: there is no `.py` in it), so a `commands/` edit
does not reach a toolbar button or a typed command name until the plugin is
rebuilt and reinstalled — see `temp/wiki_plugin_guide.md` §1.5. Only changes to
the **package** under `src/compas_masonry/` (session, scene objects, forms,
settings, splash) require the reinstall this skill performs.

**A rebuild ships `commands/`; this skill ships `src/`. Neither covers the
other** — the built `.rhp` contains no Python package at all, because every
command header declares `# r: compas_masonry>=0.2.7` and resolves it from the
site-env at run time.

RhinoCode's script editor also caches imported modules in a live interpreter,
so even after reinstalling, a bare command rerun can execute stale bytecode
from `sys.modules`.

## Process

1. Run the sync script:

   ```
   ~/.local/bin/sync-compas-masonry-rhino.sh
   ```

   Optionally pass a different repo path as `$1` (defaults to
   `~/Code/Libs/compas-Masonry`). It auto-finds the `brg-csd-*` site-env dir and
   force-reinstalls the local plugin into it with
   `--no-deps --upgrade --force-reinstall --no-build-isolation`.

2. Tell the user to reload the Python engine in Rhino's script editor, or
   fully restart Rhino if the edit touches `MasonrySession` or any other
   already-imported class (inheritance-heavy edits can leave mismatched class
   objects loaded across modules and throw
   `TypeError: super(type, obj): obj must be an instance or subtype of type`).
   A full Rhino restart always gives a clean import graph; engine reload is
   faster but only safe for leaf-level edits to modules not yet imported this
   session.

3. Verify the reinstall landed by grepping a distinctive new line in the
   site-env copy, not just the local repo — `pip install --target` silently
   no-ops on an unchanged version number unless both `--upgrade` and
   `--force-reinstall` are passed together (they are, above). Example:

   ```
   grep -n "_tag_block_materials" ~/.rhinocode/py39-rh8/site-envs/brg-csd-*/compas_masonry/session.py
   ```
