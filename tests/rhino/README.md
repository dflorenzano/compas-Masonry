# In-Rhino scratch tests

Scripts here run **inside Rhino** (open in ScriptEditor, hit play). They are not collected by pytest — they exist to make manual testing repeatable instead of remodeling geometry every time.

## Workflow

1. Run `python tests/golden/generate.py` once (outside Rhino) to produce the fixtures.
2. In Rhino, run a scratch script to load a fixture into the session and draw it.
3. Iterate on scene/drawing code; re-run the script. After editing **library** code (`src/compas_masonry/`), use ScriptEditor → *Tools → Reset Python* (or restart Rhino) — Python caches imports per session. Edits to the script itself always apply on the next run.

## Contents

- `scratch_load_golden_model.py` — load `arch_model.json` into the session and draw blocks/contacts. Tests the Model-group scene code without running any analysis.
- Add one scratch script per scenario as commands land (e.g. `scratch_load_golden_results.py` once results drawing exists).
- Keep test `.3dm` files here too (meshes ready to select, polysurfaces, etc.) — one per manual-checklist scenario.

## Manual checklist (run before each Yak release)

Per command, verify at minimum:

- [ ] command runs on a fresh document (no session) without traceback
- [ ] escape / cancel at every prompt exits cleanly
- [ ] layers created/populated as designed; re-running doesn't duplicate objects
- [ ] undo/redo leave session and scene consistent
- [ ] command works after `CM_Session_clear`

### Whole-workflow checks

The end-to-end run is `CM_Masonry_start` → blocks → contacts → supports →
material → materialassign → problem create → contactlaw → setsolver →
loads / displacements → solve → results show. Worth checking:

- [ ] **Solve reports the ipopt it found.** No ipopt means the whole solve dies inside pyomo saying nothing about `PATH` — see `REFACTOR_GUIDE.md` §1.4.
- [ ] **A CRA solve that returns `infeasible`** is usually `d_bnd`, not a modelling error (§6).
- [ ] **Results default to Forces** for CRA/RBE — Displaced is not offered at all.
- [ ] **A point load actually changes the reactions.** If it does not, the site-env's compas_cra is stale (needs `feature/external-loads`).
- [ ] **Reactions balance.** `CM_Results_print > Reactions` prints their sum; it should account for the weight of the **non-support** blocks (supports carry their own weight straight to ground).
- [ ] **Adding a load offers New-or-existing group**, and each group gets its own layer under `BoundaryConditions`.
- [ ] **A group's layer disappears when its last condition is removed** (`prune_bc_group_layers`).
- [ ] **A prescribed movement on a CRA/RBE problem warns on add and is refused at solve**, naming LMGC90/PRD/BLA.
- [ ] **`CM_Session_clear` empties the document** — no `Masonry` layers, no leftover geometry.

### After a build

Registration is only live once `rhinocode project build` has run (§1.5):

- [ ] every toolbar button launches its command (they were all dead before 2026-07-30)
- [ ] every command name is typeable on the command line
- [ ] the splash screen reflects `resources/splash/`
