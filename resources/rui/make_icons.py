"""STEP 3 — build the toolbar sprite sheet from resources/icons/<command>.svg.

This is icon System B. Toolbars do NOT use the per-command icons in the rhproj:
they use ONE PNG strip, and each command references a tile by INDEX. See
temp/wiki_icons.md §2.2.

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
from svgtools import enforce_min_stroke  # noqa: E402
from svgtools import have_rasterizer  # noqa: E402
from svgtools import rasterize  # noqa: E402
from svgtools import recolor_black  # noqa: E402
from svgtools import wrap_for_rhino  # noqa: E402

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
    # ONE sheet, ONE baked colour: the RUI format has no light/dark variant (verified
    # against Rhino's own defaultmac.rui — three SIZE slots, no theme attribute) and
    # Rhino cannot recolour a bitmap. #E6E6E6 was chosen for the old set, which was
    # drawn black and vanished on a dark toolbar. The 2026-08-28 set is drawn for a
    # light toolbar, and repainting it inverted the problem: measured over the real
    # 22-tile sheet, pixels below the 3:1 graphical minimum went 41% -> 86% on a light
    # toolbar. Shipping the artwork as drawn is the balanced option (56% dark / 41%
    # light); pass --color to trade one theme against the other.
    ap.add_argument("--color", default="", help='repaint near-black artwork ("" keeps the artwork as drawn)')

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
        # Deliberately NOT flatten_css. rsvg-convert honours the <style> block, and
        # flattening it into presentation attributes silently destroys the CSS-ONLY
        # properties: `mix-blend-mode`, `isolation` and `clip-path` have no attribute
        # form, so promoting them (PAINT_PROPS) cannot bring them back either.
        #
        # Measured 2026-08-28 over the 22-tile sheet: 8 icons rendered wrong, worst
        # CM_Problem_create at 23.5% of the tile. The failure looks like z-order gone
        # wrong, because `.k { fill: #fff }` under `mix-blend-mode: multiply` is
        # invisible by design, and without the blend it paints an opaque white block
        # over everything behind it. Reading the source verbatim is pixel-exact (max
        # deviation 0.0000%).
        #
        # System A still flattens: there Rhino renders the stored SVG itself, and
        # betting on its renderer supporting stylesheets has no upside (see svgtools).
        svg = source.read_text()
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
