"""Generate resources/COMPAS-Masonry.rui from resources/rui/ui.json.

Uses compas_rui's own RUI compiler (compas_rui.rui.Rui) — the same mechanism
BRG uses for their plugin toolbars, and compas_rui is already a plugin
dependency. Run from the repo root:

    python resources/rui/generate_rui.py

To change the layout, edit ui.json (commands / toolbars with
{"type": "separator"} items / toolbargroups) and re-run.

Icons: compas_rui embeds ONE sprite-sheet PNG referenced by index — set
icons.bitmap to the sheet path and icons.images to the ordered names, then
add "icon": <index> per command. Until then buttons have no icons.

Equivalent CLI:

    python -m compas_rui.rui resources/rui/ui.json resources/COMPAS-Masonry.rui
"""

import pathlib

from compas_rui.rui import Rui

HERE = pathlib.Path(__file__).parent
UI = HERE / "ui.json"
OUT = HERE.parent / "COMPAS-Masonry.rui"

if __name__ == "__main__":
    rui = Rui.from_json(str(UI), str(OUT))
    rui.write()
    print(f"wrote {OUT}")
