"""STEP 1 (optional) — strip every existing icon link, so the rebuild is provable.

    python resources/rui/clear_icons.py

Empties codes[].image in the rhproj and the icons block + "icon" indices in
ui.json. The build scripts REPLACE rather than merge, so this is not required —
it just makes "the old artwork is gone" something you can see rather than trust.

It never removes a codes[] entry: the entry's `id` is the command's identity to
Rhino, and a fresh one is treated as a different command.
"""

import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent.parent
RHPROJ = ROOT / "COMPAS-Masonry.rhproj"
UI = pathlib.Path(__file__).parent / "ui.json"

proj = json.loads(RHPROJ.read_text(), object_pairs_hook=collections.OrderedDict)
cleared = 0
for entry in proj["codes"]:
    if entry.pop("image", None) is not None:
        cleared += 1
RHPROJ.write_text(json.dumps(proj, indent=2) + "\n")
print(f"  rhproj: cleared {cleared} image block(s), kept all {len(proj['codes'])} entries and their ids")

ui = json.loads(UI.read_text(), object_pairs_hook=collections.OrderedDict)
ui["icons"] = {"bitmap": "", "images": []}
n = 0
for c in ui["commands"]:
    n += c.pop("icon", None) is not None
UI.write_text(json.dumps(ui, indent=4) + "\n")
print(f"  ui.json: emptied the icons block and removed {n} index/indices")
