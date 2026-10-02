# COMPAS Integration

A COMPAS Masonry session file contains the block model and its problems as COMPAS data. It can be opened in a Python script, in the Rhino Script Editor or outside Rhino, and analysed further with compas_dem.

{% hint style="warning" %}
**To do:** write this page after the Materialization page of RhinoVAULT (plan §5.6): (1) a downloadable session file and a .zip of scripts; (2) the Script Editor header lines `#! python3`, `# venv: brg-csd`, `# r: compas_masonry`; (3) load the session with `compas.json_load`, get the `BlockModel` and a `Problem`, solve, read the `Results`; (4) links to the compas_dem tutorial and examples. Check the keys of the session file against `src/compas_masonry/session.py`, and test the snippet before publishing.
{% endhint %}

## Read more

* [compas_dem tutorial](https://blockresearchgroup.github.io/compas_dem/latest/tutorial.html) (three blocks: model → problem → analysis)
* [compas_dem examples](https://blockresearchgroup.github.io/compas_dem/latest/examples.html)
* [BlockModel](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.models.BlockModel.html), [Problem](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.problem.Problem.html), [Results](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.problem.Results.html)
