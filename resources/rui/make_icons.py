"""STEP 3 — build the toolbar sprite sheet from resources/icons/<command>.svg.

This is icon System B. Toolbars do NOT use the per-command icons in the rhproj:
they use ONE PNG strip, and each command references a tile by INDEX. See
temp/ICONS.md §2.2.

    python resources/rui/make_icons.py --dry-run
    python resources/rui/make_icons.py

Writes resources/rui/icons.png (32px tiles, one row, in ui.json command order)
and the matching wiring in ui.json:

    "icons": {"bitmap": "icons.png", "images": [<command names, in order>]}
    {"name": "...", "icon": <index into that list>}

Order is taken from ui.json's own command list, so a tile's index is simply its
position there — nothing to keep in sync by hand. Run generate_rui.py afterwards.

Earlier this script composed the sheet out of the icons already embedded in the
rhproj. It now reads the SVG sources directly, so both systems are built from one
place and cannot drift.
"""

import argparse
import io
import json
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from svgtools import enforce_min_stroke, flatten_css, have_rasterizer, rasterize, recolor_black, wrap_for_rhino  # noqa: E402

TILE = 32  # compas_rui's large_bitmap item size

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
ICONS = ROOT / "resources" / "icons"
UI = HERE / "ui.json"
SHEET = HERE / "icons.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--fill-dark", default="#FFF")
    ap.add_argument("--stroke-dark", default="#FFF")
    # The sheet is a BITMAP: Rhino cannot recolour it per theme, so the colour is
    # baked here. Black artwork is near-invisible on Rhino's dark toolbar.
    ap.add_argument("--color", default="#E6E6E6", help='repaint black artwork for a dark toolbar ("" to keep black)')
    ap.add_argument("--min-stroke", type=float, default=0.6, help="floor for hairline strokes, in viewBox units (0 to disable)")
    args = ap.parse_args()

    if not have_rasterizer():
        print("rsvg-convert not found — install with:  brew install librsvg")
        return 1

    ui = json.loads(UI.read_text())

    tiles, images, missing = [], [], []
    for command in ui["commands"]:  # ui.json order == tile order == index
        name = command["name"]
        source = ICONS / f"{name}.svg"
        if not source.exists():
            missing.append(name)
            continue
        svg = flatten_css(source.read_text())
        svg = enforce_min_stroke(svg, args.min_stroke)
        svg = recolor_black(svg, args.color)
        wrapped = wrap_for_rhino(svg, args.fill_dark, args.stroke_dark)
        tiles.append(Image.open(io.BytesIO(rasterize(wrapped, TILE))).convert("RGBA"))
        images.append(name)

    if missing:
        print(f"  no icon for: {', '.join(missing)}")

    sheet = Image.new("RGBA", (TILE * len(tiles), TILE), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, (i * TILE, 0), tile)

    print(f"  sheet: {sheet.width}x{sheet.height}, {len(tiles)} tiles")
    if args.color:
        print(f"  black artwork repainted {args.color} (accent colours kept) — the sheet is a bitmap, Rhino cannot theme it")
    if args.min_stroke:
        print(f"  hairline strokes raised to {args.min_stroke} viewBox units")

    if args.dry_run:
        print("  --dry-run: nothing written")
        return 0

    sheet.save(SHEET)
    ui["icons"] = {"bitmap": SHEET.name, "images": images}
    index_of = {name: i for i, name in enumerate(images)}
    for command in ui["commands"]:
        if command["name"] in index_of:
            command["icon"] = index_of[command["name"]]
        else:
            command.pop("icon", None)
    UI.write_text(json.dumps(ui, indent=4) + "\n")
    print(f"  wrote {SHEET.relative_to(ROOT)} and {UI.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
