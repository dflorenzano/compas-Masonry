"""STEP 4 — check both icon systems before opening Rhino.

    python resources/rui/verify_icons.py

Catches the failures listed in temp/wiki_icons.md §4-5 — a missing icon, an index out of
range, a sheet that only filled one of the three button sizes — while they are
still cheap to fix.
"""

import base64
import io
import json
import pathlib
import xml.etree.ElementTree as ET

from PIL import Image

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
RHPROJ = ROOT / "COMPAS-Masonry.rhproj"
UI = HERE / "ui.json"
RUI = ROOT / "resources" / "COMPAS-Masonry.rui"

problems = []


def check(ok, message):
    print(f"  {'OK  ' if ok else 'FAIL'}  {message}")
    if not ok:
        problems.append(message)


def main():
    proj = json.loads(RHPROJ.read_text())
    ui = json.loads(UI.read_text())
    commands = {p.stem for p in (ROOT / "commands").glob("CM_*.py")}

    print("System A — rhproj, per command")
    without = [c["title"] for c in proj["codes"] if not ((c.get("image") or {}).get("light") or {}).get("data")]
    check(not without, f"every entry has an SVG ({len(proj['codes'])} entries)" if not without else f"no SVG: {without}")
    nodark = [
        c["title"]
        for c in proj["codes"]
        if (d := ((c.get("image") or {}).get("light") or {}).get("data")) and "fill-dark" not in base64.b64decode(d).decode("utf-8", "replace")
    ]
    check(not nodark, "every SVG carries fill-dark (dark theme)" if not nodark else f"no fill-dark: {nodark}")

    print("System B — toolbar sprite sheet")
    icons = ui.get("icons") or {}
    check(bool(icons.get("bitmap")), f"icons.bitmap set ({icons.get('bitmap') or 'EMPTY'})")
    images = icons.get("images") or []
    indexed = [c for c in ui["commands"] if "icon" in c]
    check(len(indexed) == len(ui["commands"]), f"every command has an icon index ({len(indexed)}/{len(ui['commands'])})")
    bad = [c["name"] for c in indexed if not 0 <= c["icon"] < len(images)]
    check(not bad, f"every index is in range (0..{len(images) - 1})" if not bad else f"out of range: {bad}")
    mismatch = [c["name"] for c in indexed if 0 <= c["icon"] < len(images) and images[c["icon"]] != c["name"]]
    check(not mismatch, "index points at the command's own tile" if not mismatch else f"index/name mismatch: {mismatch}")

    print("Compiled RUI")
    if not RUI.exists():
        check(False, "COMPAS-Masonry.rui exists — run generate_rui.py")
    else:
        root = ET.parse(RUI).getroot()

        # THE important one. Rhino reads the .rui and nothing else, so a sheet
        # rebuilt after the last compile leaves the toolbars showing the previous
        # artwork with every other check still passing. This is the exact failure
        # that got shipped on 2026-08-05: make_icons.py ran, generate_rui.py did not.
        sheet = HERE / (icons.get("bitmap") or "")
        if sheet.is_file():
            embedded = base64.b64decode((root.find("bitmaps").find("large_bitmap").find("bitmap").text or "").strip())
            check(
                embedded == sheet.read_bytes(),
                f"the .rui embeds the CURRENT {sheet.name}" if embedded == sheet.read_bytes() else f"the .rui was compiled from a DIFFERENT {sheet.name} — re-run generate_rui.py",
            )

        counts = {}
        for size in ("small_bitmap", "normal_bitmap", "large_bitmap"):
            e = root.find("bitmaps").find(size)
            raw = base64.b64decode((e.find("bitmap").text or "").strip())
            counts[size] = (Image.open(io.BytesIO(raw)).size, len(e.findall("bitmap_item")))
        for size, (dims, items) in counts.items():
            check(items == len(images) and dims[0] >= dims[1] * max(items, 1) * 0.9, f"{size}: {dims[0]}x{dims[1]}, {items} tiles")
        withicon = sum(1 for m in root.iter("macro_item") if m.get("bitmap_id"))
        check(withicon == len(images), f"{withicon} macros carry a bitmap_id")

    print("Names")
    check(commands == {c["title"] for c in proj["codes"]}, "rhproj titles match commands/")
    check(commands == {c["name"] for c in ui["commands"]}, "ui.json names match commands/")

    print()
    print(f"{len(problems)} problem(s)" if problems else "all checks passed")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
