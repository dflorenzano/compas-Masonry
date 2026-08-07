"""STEP 2 — bind resources/icons/<command>.svg into COMPAS-Masonry.rhproj.

This is icon System A: one SVG per command, stored inline, driving the Script
Editor and the command palette. See temp/wiki_icons.md §2.1.

For each codes[] entry it REPLACES image wholesale — flattening the CSS, wrapping
the icon in Rhino's dark-aware outer SVG, and rendering the 24x24 light/dark PNG
cache. Replacing rather than merging is what removes any link to the old artwork.

    python resources/rui/set_rhproj_icons.py --dry-run
    python resources/rui/set_rhproj_icons.py

The entry's `id` is never touched: it is the identity of the command as far as
Rhino is concerned, and a new one makes Rhino treat it as a different command.
"""

import argparse
import base64
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from svgtools import flatten_css, have_rasterizer, rasterize, wrap_for_rhino  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent.parent
RHPROJ = ROOT / "COMPAS-Masonry.rhproj"
ICONS = ROOT / "resources" / "icons"
RENDER = 24  # the size the rhproj caches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--fill-dark", default="#FFF")
    ap.add_argument("--stroke-dark", default="#FFF", help='"none" for filled artwork')
    args = ap.parse_args()

    proj = json.loads(RHPROJ.read_text(), object_pairs_hook=collections.OrderedDict)

    if not have_rasterizer():
        print("rsvg-convert not found — install with:  brew install librsvg")
        return 1

    done, missing = 0, []
    for entry in proj["codes"]:
        name = entry["title"]
        source = ICONS / f"{name}.svg"
        if not source.exists():
            missing.append(name)
            continue

        wrapped = wrap_for_rhino(flatten_css(source.read_text()), args.fill_dark, args.stroke_dark)
        png = base64.b64encode(rasterize(wrapped, RENDER)).decode()

        entry["image"] = collections.OrderedDict(
            [
                ("light", collections.OrderedDict([("type", "svg"), ("data", base64.b64encode(wrapped.encode()).decode())])),
                (
                    "rendered",
                    collections.OrderedDict(
                        [
                            ("light", collections.OrderedDict([("bytes", png), ("width", RENDER), ("height", RENDER)])),
                            ("dark", collections.OrderedDict([("bytes", png), ("width", RENDER), ("height", RENDER)])),
                        ]
                    ),
                ),
            ]
        )
        done += 1

    if missing:
        print(f"  no icon for: {', '.join(missing)}")
    print(f"  {done}/{len(proj['codes'])} entries given an icon from {ICONS.relative_to(ROOT)}")

    if args.dry_run:
        print("  --dry-run: nothing written")
        return 0

    RHPROJ.write_text(json.dumps(proj, indent=2) + "\n")
    print(f"  wrote {RHPROJ.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
