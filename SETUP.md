# Setting up COMPAS Masonry from source

From `git clone` to a working toolbar in Rhino 8, running **this repository's**
code rather than the published package.

Written for macOS, where every command below was executed. Windows differs only
in paths — see §6.

---

## 0. What you need first

| | |
|---|---|
| **Rhino 8** | installed and launched at least once |
| **git**, **python3** | any recent version, for the build scripts |
| **~1.5 GB free** | the install peaks there before §5 trims it back to ~300 MB |

No `ipopt`, no PATH setup, no conda environment. `compas_cra` 0.8.0 carries a
native solver inside the wheel. Any instruction telling you to install `ipopt`
by hand predates it.

You do **not** need `rsvg-convert` / `librsvg`: the compiled toolbar
(`resources/COMPAS-Masonry.rui`) and icon sheet are committed, and step 2 skips
the icon pipeline.

---

## 1. Clone

```bash
git clone https://github.com/dflorenzano/compas-Masonry.git
cd compas-Masonry
```

## 2. Build the plugin

```bash
./resources/rui/build_plugin.sh 0.1.57-beta --skip-icons
```

Bump the version on **every** later rebuild. Rhino keys packages by version and
installs them side by side, so reusing one invites a stale load.

The script builds, asserts by md5 that the archive carries the designed toolbar
rather than the one `rhinocode` generates, then **stops before installing** and
prints the exact install command.

## 3. Install it

**Quit Rhino first** — `yak` cannot replace a loaded plugin.

Run the line the script printed. It looks like this, but the `+NNNNN` build
suffix is computed, so copy the printed one rather than typing this:

```bash
"/Applications/Rhino 8.app/Contents/Resources/bin/yak" install \
    --source "$PWD/build/rh8-mac" COMPAS-Masonry 0.1.57-beta+NNNNN
```

A wrong name or version prints `[error] No package found by the name of...`,
which reads like a network failure and is not one. The package is
`COMPAS-Masonry` — not the lowercased archive filename.

## 4. Let Rhino create its Python environment

**Start Rhino. Run any `CM_` command once** — `CM_Session_start` will do.

**It will fail. That is expected and required.** Rhino keeps a private Python
environment per plugin, and it does not exist until a command asks for it. The
next steps install into that environment, so it has to exist first — and its
folder name carries a per-machine hash, so it cannot be created by hand.

**Quit Rhino.**

## 5. Install the dependencies

```bash
PY=~/.rhinocode/py39-rh8/python3.9
SE=$(echo ~/.rhinocode/py39-rh8/site-envs/brg-csd-*)
echo "$SE"     # sanity check: ONE path, ending in brg-csd-XXXXXXXX
```

If that prints a literal `*`, step 4 did not happen — go back and run a command
in Rhino.

```bash
"$PY" -m pip install --target "$SE" --upgrade -r requirements.txt
```

**This is not optional, and not what step 4 already did.** The published
`compas_masonry` package's metadata — which is what Rhino resolved in step 4 —
lists *no solver backends at all*: no `compas_cra`, `compas_lmgc90`,
`compas_3dec`, `pyomo` or `compas_rbe`. Without this step there is nothing to
solve with.

Then drop the Qt stack:

```bash
rm -rf "$SE"/PySide6* "$SE"/shiboken6* "$SE"/compas_viewer*
```

`compas_lmgc90` declares `compas_viewer` as a hard requirement — an upstream
packaging bug, everyone else puts it behind a `viz` extra — and that pulls in
PySide6: **1.1 GB of a 1.4 GB install**. Nothing in the plugin imports it. The
only module that does is `src/compas_masonry/viewers/masonryviewer.py`, which
has no importers anywhere in the codebase. Removing it leaves ~291 MB.

## 6. Install this repository's package

```bash
"$PY" -m pip install --target "$SE" \
    --no-deps --upgrade --force-reinstall --no-build-isolation .
```

**Also not redundant with step 5.** `requirements.txt` installs the
dependencies, not this repo. Step 4 installed the *published* `compas_masonry`,
which is missing `results.py`, `solvers.py`, `sessionio.py` and `inputs.py` —
and reports the **same version number** as the local build, so nothing detects
the difference. Skip this and you run the old package under a version string
that says otherwise.

`--upgrade` **and** `--force-reinstall` are both required: `pip install
--target` silently does nothing when the version has not changed, which is
exactly this case.

## 7. Verify before trusting it

```bash
python3 resources/rui/verify_install.py
```

Should print `up to date — every command in the repo is the one installed`. It
compares every command in `commands/` against the copy embedded in the built
plugin, so it catches a stale build that a version number would not.

```bash
ls "$SE/compas_masonry/solvers.py"                      # must exist
grep -c Analysis "$SE/compas_dem/models/__init__.py"    # >= 1

# no package installed twice — a duplicate makes pip report the WRONG version
ls -d "$SE"/*.dist-info | sed 's|.*/||;s|-[0-9][^-]*\.dist-info$||' \
  | tr 'A-Z' 'a-z' | sort | uniq -d                     # must print nothing
```

```bash
"$PY" -c "
import sys; sys.path.insert(0, '$SE')
import importlib.metadata as md
from compas_dem.models import Analysis
from compas_dem.problem import Solver
from compas_cra.equilibrium import cra_solve
for p in ['compas', 'compas_dem', 'compas_cra', 'compas_3dec', 'compas_lmgc90', 'compas_masonry']:
    print(' ', p, md.version(p))
print('  ThreeDEC:', hasattr(Solver, 'ThreeDEC'))"
```

Expected:

```
  compas 2.15.1
  compas_dem 0.6.0
  compas_cra 0.8.0
  compas_3dec 0.2.0
  compas_lmgc90 0.1.11
  compas_masonry 0.3.0
  ThreeDEC: True
```

Do **not** add `compas_masonry.inputs` to that check — it imports `Rhino` at
module level and cannot load outside Rhino.

## 8. Start Rhino

A full start, not an engine reload: `MasonrySession` is a singleton captured at
import, so a reload can leave mismatched class objects across modules.

The `COMPAS Masonry` toolbar should appear. `CM_Session_start` should now run.

If the toolbar comes up undocked or in an odd position, that is not a failed
build — toolbar guids are minted fresh on every build. Drag it back.

---

## Running the tests

Independent of Rhino, on any Python 3.9+:

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src python3 -m pytest tests/ -q     # 174 passed, 1 skipped
ruff check commands/ src/ tests/
```

The one skip is `test_golden`, which needs a generated fixture.

---

## After you change something

**A rebuild ships `commands/`. Reinstalling the package ships
`src/compas_masonry/`. Neither covers the other.**

| Changed | Run | Then |
|---|---|---|
| `src/compas_masonry/**` | step 6 | restart Rhino |
| `commands/**` | steps 2 + 3 (**bump the version**) | restart Rhino |
| both | 6, then 2 + 3 | restart Rhino |
| artwork, `resources/rui/ui.json` | steps 2 + 3 **without** `--skip-icons` (needs `librsvg`) | restart Rhino |

The Script Editor is the exception: it runs `commands/*.py` straight from the
repo, so a command tested there is **not** evidence about a toolbar button.

---

## §6. Windows

Steps 1, 5, 6 and 7 are identical apart from paths:

| | macOS | Windows |
|---|---|---|
| `yak`, `rhinocode` | `/Applications/Rhino 8.app/Contents/Resources/bin/` | `C:\Program Files\Rhino 8\System\` |
| Rhino's Python | `~/.rhinocode/py39-rh8/python3.9` | `%USERPROFILE%\.rhinocode\py39-rh8\` |

`build_plugin.sh` is a bash script: use Git Bash or WSL, or run its steps by
hand.

**These Windows paths have not been verified on a Windows machine** — check them
rather than assuming.

3DEC runs **only** on Windows: it drives a licensed Itasca 3DEC installation
that `compas_3dec` discovers under `Program Files\Itasca`. On macOS and Linux a
3DEC solve is refused up front, before any prompt. CRA, RBE and LMGC90 work
everywhere.

---

## If something goes wrong

**A command fails with `ImportError: cannot import name 'Analysis'`** — the
environment was re-resolved and `compas_dem` was replaced by an older published
version that lacks it. Re-run step 5.

**A command fails on `compas_masonry.results` or `solvers`** — step 6 did not
take, or was undone by a later install. Re-run it, then `verify_install.py`.

**`pip` reports a version that does not match what is on disk** — two
`.dist-info` folders for one package. Find them with the duplicate check in step
7 and delete the older. The comparison must be case-insensitive: `Pyomo` and
`pyomo` are the same package.

**A toolbar button behaves like old code** — `verify_install.py`. A build only
picks up `commands/` as they were when it ran.

**Installing the plugin broke the environment** — installing makes Rhino
re-resolve dependencies, and both `compas_masonry` and `compas_dem` exist on
PyPI at version strings matching local builds, so an older release can be
installed over a newer one with nothing able to tell them apart. Re-run steps 5
and 6, then verify.
