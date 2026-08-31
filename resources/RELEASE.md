# Shipping a maintenance change to Rhino

How to get an edit out of this repo and into a running Rhino, and how to prove it
arrived. Written for the small-change loop — a bug fix, a new setting, a reworded
message — not for a public release.

Everything here was executed on 2026-08-31 against `0.1.57-beta+33689`; the
commands are the ones that ran, not reconstructions.

---

## 1. The one rule

**A rebuild ships `commands/`. A sync ships `src/compas_masonry/`. Neither covers
the other.**

They are two different mechanisms and neither reports on the other's state:

- Every command file carries `# r: compas_masonry>=0.2.7` in its header. Rhino
  resolves that **at run time** from the site-env, so the built plugin contains
  no Python package at all — only the command scripts.
- The command scripts are **embedded in `COMPAS-Masonry.rhp`** at build time.
  Editing `commands/CM_Foo.py` does not reach a toolbar button or a typed command
  name until the plugin is rebuilt and reinstalled.

The Script Editor is the exception: it runs `commands/*.py` straight from the repo
path, so a failing toolbar button is **not** evidence about code you just synced.

### What did you change?

| Changed | Run | Then |
|---|---|---|
| `src/compas_masonry/**` only | sync (§2) | restart Rhino |
| `commands/**` only | rebuild + install (§3) | restart Rhino |
| both | sync **then** rebuild + install | restart Rhino |
| `resources/rui/**` (artwork, `ui.json`) | rebuild + install, **without** `--skip-icons` | restart Rhino |
| tests, docs, CHANGELOG | nothing | — |

**Full Rhino restart, not an engine reload.** `MasonrySession` is a singleton
grabbed as a class attribute at import, and `RhinoBlockObject` grabs it too, so a
reload can leave mismatched class objects across modules and throw
`TypeError: super(type, obj): obj must be an instance or subtype of type`.

---

## 2. Syncing the package (`src/`)

```bash
~/.local/bin/sync-compas-masonry-rhino.sh
```

It finds the `brg-csd-*` site-env itself and reinstalls the local package with
`--target --no-deps --upgrade --force-reinstall --no-build-isolation`.

Two consequences of those flags, both deliberate:

- `--upgrade --force-reinstall` **together** are required. `pip install --target`
  silently no-ops on an unchanged version number, and the version has not changed
  in a while — without both flags the sync appears to succeed and ships nothing.
- `--no-deps` means the sync updates the package and its metadata but installs no
  new requirements. Add a dependency to `requirements.txt` and you must install it
  into the site-env yourself.

Verify against the **site-env copy**, never against pip's stdout:

```bash
SE=$(echo ~/.rhinocode/py39-rh8/site-envs/brg-csd-*)
diff -rq src/compas_masonry "$SE/compas_masonry" | grep -v __pycache__   # empty
```

---

## 3. Rebuilding and installing (`commands/`)

```bash
./resources/rui/build_plugin.sh 0.1.58-beta --bump-rhproj --skip-icons
```

**Bump the version on every rebuild.** Rhino keys packages by version and installs
them side by side; reusing a version invites a stale load. The script refuses to
run without one.

- `--bump-rhproj` writes the version into `COMPAS-Masonry.rhproj` so the project
  file stops lagging the builds.
- `--skip-icons` skips regenerating the icon sheet and the `.rui`. Correct when
  artwork has not changed — it is faster and avoids re-running
  `set_rhproj_icons.py`, which still flattens CSS (a known defect for the palette
  icons). **Drop it whenever you touch artwork or `ui.json`.**

The script runs seven steps, asserts by md5 that the archive carries **your**
designed toolbar rather than the one `rhinocode project build` generates, then
**stops before installing** and prints the install command.

**Use the printed line verbatim.** The package name is `COMPAS-Masonry` — not the
lowercased archive filename — and the version carries a `+<build>` suffix that is
neither what you passed to the script nor what is in the `.yak` filename. Getting
either wrong prints:

```
[error] No package found by the name of...
```

which reads like a network failure and is not one.

**Quit Rhino before installing.** `yak install` cannot replace a loaded plugin.

---

## 4. Proving it arrived

Three checks, cheapest first. Do at least the second.

### 4.1 Which version is active

```bash
cat ~/Library/"Application Support"/McNeel/Rhinoceros/packages/8.0/COMPAS-Masonry/manifest.txt
```

`manifest.txt` names the version Rhino loads. Older versions stay on disk beside
it, so **a directory listing is not the answer** — if you see old behaviour, read
this file before concluding the build failed.

### 4.2 That the package carries your commands — the one that matters

```bash
python3 resources/rui/verify_install.py
```

A version bump proves a build happened, not what went into it. This decodes the
project blob embedded in the `.rhp` and compares **every** command against the
file in the repo:

```
active package : 0.1.57-beta+33689
also on disk   : 0.1.56-beta+35367  (not loaded)
commands       : 28 embedded, 28 in the repo

up to date — every command in the repo is the one installed
```

Exits 1 and names the offenders when something drifted, so it can gate a test
session. Its counterpart is `verify_icons.py`, which answers the same question for
artwork.

### 4.3 That the install did not wreck the site-env

**Run this after every install.** See §5.

```bash
SE=$(echo ~/.rhinocode/py39-rh8/site-envs/brg-csd-*)
grep -c Analysis "$SE/compas_dem/models/__init__.py"    # >= 1   (0 = clobbered)
ls "$SE/compas_masonry/solvers.py"                       # must exist
diff -rq src/compas_masonry "$SE/compas_masonry" | grep -v __pycache__   # empty
ls -d "$SE"/*.dist-info | sed 's|.*/||;s|-[0-9][^-]*\.dist-info$||' \
  | tr 'A-Z' 'a-z' | sort | uniq -d                      # empty
```

---

## 5. Landmines

### Installing can silently replace your packages with older PyPI ones

Installing makes RhinoCode resolve `# r: compas_masonry>=0.2.7` and pull the
plugin's `Requires-Dist`. **Both `compas_masonry` and `compas_dem` are on PyPI at
version strings that match what is in the site-env**, so pip can install an older
release over a newer local one and nothing — not pip, not the `dist-info`, not
`importlib.metadata` — can tell them apart. Only file contents differ.

This has happened once for real: on 2026-08-28 an install replaced a working
`compas_dem` with PyPI 0.5.0, which had no `Analysis`, and every command died.

PyPI `compas_masonry` 0.3.0 is the same trap waiting: it carries no `results.py`,
`solvers.py`, `sessionio.py` or `inputs.py`, while calling itself 0.3.0 exactly
like the local build. The §4.3 checks are what catch it. The fix is to re-run the
sync (§2).

### `pip install --target` never uninstalls

Two `*.dist-info` folders for one package make the metadata lookup return the
**wrong** version — observed with `compas_lmgc90` (0.1.10 on disk, 0.1.9
reported) and again with `compas_cra` (0.8.0 on disk, 0.5.0 reported). Sweep with
the case-insensitive check in §4.3: the comparison **must** ignore case, because
`Pyomo-6.8.2` and `pyomo-6.4.2` are one package and a case-sensitive sweep misses
it. Before deleting a `dist-info`, confirm the newer `RECORD` covers every
still-present file the older one claims.

Cross-check a version by comparing `importlib.metadata.version()` against the
package's own `__version__`. They disagree exactly when this has happened.

### Toolbar guids are minted fresh on every build

Only `COLLECTION_GUID` is pinned, so expect the tab to come back undocked after a
layout change. **Not a failed build** — the giveaway is correct buttons and correct
artwork in an odd position.

### A second COMPAS-Masonry tab

That is the copy opened by hand from `resources/`, not a duplicate install. Close
it in Tools > Toolbar Layout.

### The embedded command sources are base64 twice

Only relevant if you inspect a `.rhp` by hand. `codes[].text` inside the project
blob is base64-encoded **twice**; decode once and what comes back is more base64,
in which no marker is ever found — which reads exactly like "the command is
missing from the package" and will send you rebuilding something already correct.
`verify_install.py` decodes until it sees the `#! python3` shebang.

---

## 6. Rolling back

Rhino keeps every installed version, so switching back is a reinstall of the older
one — it is still on disk:

```bash
ls ~/Library/"Application Support"/McNeel/Rhinoceros/packages/8.0/COMPAS-Masonry/

OLDER=0.1.56-beta+35367          # a version from that listing
"/Applications/Rhino 8.app/Contents/Resources/bin/yak" install \
    --source build/rh8-mac COMPAS-Masonry "$OLDER"
```

(Placeholders are shell variables rather than `<angle brackets>` on purpose —
`<` is a redirect, so an unedited paste fails with a parse error instead of an
obvious complaint about the missing value.)

For the site-env, back up before an install that might touch it — a package plus
its `dist-info` is small:

```bash
SE=$(echo ~/.rhinocode/py39-rh8/site-envs/brg-csd-*)
( cd "$SE" && tar czf ~/se_backup.tgz compas_dem compas_dem-*.dist-info \
                                       compas_masonry compas_masonry-*.dist-info )
```

About 300 KB, ~170 entries.

The `cd` is not cosmetic. `tar -C "$SE" compas_dem-*.dist-info` **fails in zsh**:
the shell expands the glob before tar ever sees it, against the *current*
directory rather than `-C`'s, and aborts with `no matches found`. The subshell
makes the glob and the archive agree about where they are.

Restore with `tar xzf ~/se_backup.tgz -C "$SE"`, then remove any newer
`dist-info` the failed install left behind.

---

## 7. Removing an old version

Every rebuild leaves a version folder behind — `--bump-rhproj` guarantees a new
one each time — so they accumulate at ~3.8 MB each. They are inert once Rhino has
started on the new one, and `yak list` reports only the active version, not the
leftovers.

**The order matters, and getting it wrong looks like a bad build.**

### Wait until Rhino has started on the new version

`manifest.txt` names the version Rhino *will* load, but two of Rhino's own
settings files record the version it **last ran**, by absolute path:

```
8.0/settings/settings-Scheme__Default.xml        -> …/<version>/COMPAS-Masonry.rhp   (plugin registry)
8.0/settings/Scheme__Default/containers.xml      -> …/<version>/COMPAS-Masonry.rui   (toolbar layout)
```

`yak install` does not touch either — Rhino rewrites them on its next start. So in
the window between installing and restarting, **both still point into the OLD
folder**. Observed 2026-08-31: `containers.xml` written 18:42, the new package
installed 18:43:24, and neither settings file mentioned the new version.

Delete the old folder in that window and Rhino comes up pointing at a missing
`.rhp` and `.rui`: the plugin may fail to load and the toolbar may vanish, which
reads exactly like the build being broken.

### The sequence

1. Start Rhino. It loads the version `manifest.txt` names and repoints both
   settings files.
2. Confirm the handover, then quit Rhino:

```bash
S=~/Library/"Application Support"/McNeel/Rhinoceros/8.0/settings
NEW=$(cat ~/Library/"Application Support"/McNeel/Rhinoceros/packages/8.0/COMPAS-Masonry/manifest.txt)
grep -c "$NEW" "$S/Scheme__Default/containers.xml"      # >= 1
grep -c "$NEW" "$S/settings-Scheme__Default.xml"        # >= 1
```

3. Remove the old folder:

```bash
P=~/Library/"Application Support"/McNeel/Rhinoceros/packages/8.0/COMPAS-Masonry
OLD=0.1.56-beta+35367            # any version from `ls "$P"` that is not in manifest.txt
rm -rf "$P/$OLD"
```

### Do NOT use `yak uninstall`

```
yak uninstall <package>...
```

It takes a package **name**, not a version, and `yak list` sees only the active
one — so `yak uninstall COMPAS-Masonry` removes the whole package including the
version you are using.

### When to bother

Keep the previous version until the new one has been exercised: it is the rollback
path in §6, and reinstalling it is one command. Prune afterwards, and routinely,
since the folders accumulate one per build.

---

## 8. The whole loop, for a change touching both halves

```bash
cd ~/Code/Libs/compas-Masonry

PYTHONPATH=src python3 -m pytest tests/ -q      # 167 passed, 1 skipped
ruff check commands/ src/ tests/
python3 resources/rui/verify_icons.py

~/.local/bin/sync-compas-masonry-rhino.sh       # ships src/

./resources/rui/build_plugin.sh 0.1.58-beta --bump-rhproj --skip-icons
# QUIT RHINO, then run the yak line it printed

python3 resources/rui/verify_install.py         # ships commands/ -- confirm
SE=$(echo ~/.rhinocode/py39-rh8/site-envs/brg-csd-*)
grep -c Analysis "$SE/compas_dem/models/__init__.py"
diff -rq src/compas_masonry "$SE/compas_masonry" | grep -v __pycache__

# start Rhino fresh
```

## 9. See also

- `resources/rui/verify_icons.py` — did the artwork ship
- `resources/rui/verify_install.py` — did the code ship
- `.claude/skills/sync-compas-masonry/` and `sync-compas-dem/` — the sync half
- `temp/wiki_icons.md` — icon pipeline and toolbar layout (**gitignored**, local only)
