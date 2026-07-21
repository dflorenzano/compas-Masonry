---
name: sync-compas-dem
description: >
  Sync local edits to the compas_dem repo into Rhino's RhinoCode site-env so
  the script editor picks them up. Use when the user edited compas_dem source
  (e.g. src/compas_dem/models/blockmodel.py) and needs Rhino to see the
  change, or reports a Rhino traceback pointing at
  .rhinocode/py39-rh8/site-envs/.../compas_dem/... that doesn't match what's
  in the local repo. Trigger phrases: "sync compas_dem", "update compas_dem
  in rhino", "push my compas_dem changes to rhino", "reinstall compas_dem".
---

# Sync compas_dem into Rhino

## Why this exists

The Rhino site-env at `~/.rhinocode/py39-rh8/site-envs/brg-csd-*/` is a flat
`pip install --target` dump, not an editable install. Editing
`~/Code/Libs/compas_dem` never touches it — Rhino keeps importing the old
pip-installed copy until it's manually reinstalled. On top of that, RhinoCode's
script editor caches imported modules in a live interpreter, so even after
reinstalling, a bare script rerun can still execute stale bytecode from
`sys.modules`.

## Process

1. Run the sync script:

   ```
   ~/.local/bin/sync-compas-dem-rhino.sh
   ```

   Optionally pass a different repo path as `$1` if syncing a different local
   COMPAS library (defaults to `~/Code/Libs/compas_dem`). It auto-finds the
   `brg-csd-*` site-env dir and force-reinstalls the local repo into it with
   `--no-deps --upgrade --force-reinstall --no-build-isolation`.

2. Tell the user to reload the Python engine in Rhino's script editor, or
   fully restart Rhino if the edit touches base/inheritance-heavy classes
   (e.g. anything under `compas.datastructures`, `compas.data`) — a partial
   engine reload can leave mismatched class objects loaded across modules
   and throw `TypeError: super(type, obj): obj must be an instance or
   subtype of type`. A full Rhino restart always gives a clean import graph;
   engine reload is faster but only safe for leaf-level edits.

3. Verify the fix landed by grepping the target file inside the site-env
   copy, not just the local repo — e.g.:

   ```
   grep -n "<distinctive new line>" ~/.rhinocode/py39-rh8/site-envs/brg-csd-*/compas_dem/models/blockmodel.py
   ```

   Don't assume the reinstall worked from stdout alone — `pip install --target`
   silently no-ops on unchanged version numbers unless both `--upgrade` and
   `--force-reinstall` are passed together.
