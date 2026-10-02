# FAQ

## Frequently Asked Questions

### Why does Rhino's Undo not undo a COMPAS Masonry command?

COMPAS Masonry keeps its own history. Use `CM_Session_undo` and `CM_Session_redo`; see [6. Utilities](../manual/6-utilities.md).

### Why is my problem refused by CRA or RBE?

CRA and RBE solve self-weight only. A problem with loads or prescribed displacements must be solved with LMGC90 or 3DEC; see [2c. Solver](../manual/2-problem/solver.md).

### Where can I report a bug or request a feature?

Use the [issue tracker](https://github.com/BlockResearchGroup/compas-Masonry/issues) or the [COMPAS forum](https://forum.compas-framework.org/).

{% hint style="warning" %}
**To do:** more questions as they come up (e.g. macOS / Windows differences).
{% endhint %}
