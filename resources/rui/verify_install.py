"""Check that the INSTALLED plugin runs the commands now in the repo.

Why this exists
---------------
A rebuild ships `commands/`; a sync ships `src/`. Neither covers the other, and
nothing else in the toolchain reports whether a toolbar button is running today's
code. A version bump proves only that *a* build happened — not what went into it
— and Rhino installs versions side by side, so an old package sitting next to a
new one looks identical in Finder while `manifest.txt` quietly decides which one
loads. The failure mode is silent and expensive: you test the previous build,
find the bug you just fixed, and go looking for it in code that is already
correct.

`verify_icons.py` answers "did my artwork ship". This answers "did my code ship".

Where the sources actually live
-------------------------------
Not as `.py` files. `rhinocode project build` embeds the whole project into
`COMPAS-Masonry.rhp` as one base64 blob of JSON; the `.cs` files beside it are
only C# stubs mapping a command name to a GUID, and the `.rhproj` in the repo
references `commands/*.py` by `uri` rather than carrying their text.

**`codes[].text` inside that JSON is base64 A SECOND TIME.** Decode once and what
comes back is more base64, in which no marker is ever found — which reads exactly
like "the command is missing from the package" and will send you off to rebuild
something that was already correct. Decode until the payload starts with the
`#! python3` shebang every command carries.

Usage
-----
    python3 resources/rui/verify_install.py            # repo = cwd
    python3 resources/rui/verify_install.py <repo>

Exits 1 if any command in the repo differs from the installed one, so it can gate
a rehearsal.
"""

import base64
import json
import pathlib
import subprocess
import sys

PACKAGES = pathlib.Path.home() / "Library/Application Support/McNeel/Rhinoceros/packages/8.0/COMPAS-Masonry"


def embedded_commands(rhp: pathlib.Path) -> dict:
    """`{command title: source}` for every command inside a built .rhp."""
    strings = subprocess.run(["strings", str(rhp)], capture_output=True, text=True).stdout.splitlines()
    if not strings:
        sys.exit(f"nothing readable in {rhp}")

    # The project blob is by far the largest string in the binary — several
    # hundred KB against ~200 bytes for anything else.
    blob = max(strings, key=len)

    # `strings` can pick up a stray leading byte before the base64 actually
    # starts, so step forward until the payload decodes to JSON.
    for skip in range(8):
        candidate = blob[skip:]
        try:
            raw = base64.b64decode(candidate + "=" * (-len(candidate) % 4))
        except Exception:
            continue
        if raw[:1] == b"{":
            break
    else:
        sys.exit(f"could not find the embedded project blob in {rhp}")

    commands = {}
    for code in json.loads(raw).get("codes", []):
        text = code["text"]
        # decode until the shebang appears — see the module docstring
        for _ in range(4):
            try:
                text = base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", "replace")
            except Exception:
                text = ""
                break
            if text.lstrip().startswith("#!"):
                break
        commands[code["title"]] = text
    return commands


def main() -> int:
    repo = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    commands_dir = repo / "commands"
    if not commands_dir.is_dir():
        sys.exit(f"no commands/ under {repo}")

    manifest = PACKAGES / "manifest.txt"
    if not manifest.exists():
        sys.exit(f"no installed COMPAS-Masonry package ({manifest} not found)")

    # manifest.txt names the version Rhino loads. Other versions stay on disk
    # beside it, so the directory listing is NOT the answer.
    version = manifest.read_text().strip()
    print(f"active package : {version}")
    siblings = sorted(p.name for p in PACKAGES.iterdir() if p.is_dir() and p.name != version)
    if siblings:
        print(f"also on disk   : {', '.join(siblings)}  (not loaded)")

    installed = embedded_commands(PACKAGES / version / "COMPAS-Masonry.rhp")
    on_disk = sorted(commands_dir.glob("CM_*.py"))
    print(f"commands       : {len(installed)} embedded, {len(on_disk)} in the repo")

    stale = []
    for path in on_disk:
        theirs = installed.get(path.stem)
        if theirs is None:
            stale.append((path.stem, "not in the package"))
        elif theirs.strip() != path.read_text().strip():
            stale.append((path.stem, "differs from the repo"))

    for name, why in stale:
        print(f"  STALE  {name:<26} {why}")

    if stale:
        print(f"\n{len(stale)} stale — rebuild and reinstall before testing through the toolbar")
        return 1

    print("\nup to date — every command in the repo is the one installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
