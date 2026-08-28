# COMPAS Masonry

> [!WARNING]
> This plugin is under active development,
> and its functionality will frequently change.

![COMPAS Masonry](compas-Masonry.png)

COMPAS Masonry is a plugin for Rhino for the assessment of masonry structures,
and for the stability analsis of Discrete Element Models in general.

The current version of this plugin is based on COMPAS 2 and is only available for Rhino 8.

## Installation

To install COMPAS-Masonry, use Rhino's package manager Yak.
To open Yak, type `PackageManager` on the Rhino command line.
Then search for "COMPAS Masonry" and install.

## COMPAS Packages

COMPAS-Masonry uses the following COMPAS packages:

* [compas](https://github.com/compas-dev/compas)
* [compas_cgal](https://github.com/compas-dev/compas_cgal)
* [compas_dem](https://github.com/blockresearchgroup/compas_dem)
* [compas_libigl](https://github.com/compas-dev/compas_libigl)
* [compas_model](https://github.com/blockresearchgroup/compas_model)
* [compas_rui](https://github.com/blockresearchgroup/compas_rui)
* [compas_session](https://github.com/blockresearchgroup/compas_session)
* [compas_tna](https://github.com/blockresearchgroup/compas_tna)
* [compas_tno](https://github.com/blockresearchgroup/compas_tno)

After installing COMPAS-Masonry with Yak, these requirements will be installed automatically if necessary.
The tool might be unresponsive during this process, which might take up to 1 or 2 mins.
The packages are installed in a separate virtual environment named `COMPAS-Masonry`.

## Solvers

Equilibrium analysis runs through [compas_cra](https://github.com/blockresearchgroup/compas_cra):

* **RBE** — rigid block equilibrium
* **CRA** — coupled rigid block analysis, with an optional penalty formulation

Both return **contact forces** rather than displacements, and both solve through
the `ipopt` executable, which must be on the `PATH` Rhino sees.

> [!IMPORTANT]
> These need **compas_cra >= 0.6.0**, which is on PyPI and pulls **pyomo >= 6.7**
> with it, so no manual install step is required any more. The older compas_cra
> 0.4.0 cannot be used in a NumPy 2 environment.
>
> compas_cra still solves for self-weight only — `external_force_setup(assembly,
> density)` takes no external load vector as of 0.6.0. A problem carrying any
> boundary condition is therefore refused by `check_ready()` and has to go to
> LMGC90 or 3DEC instead.

**LMGC90** provides contact dynamics and displacements in-process through
`compas_lmgc90`.

**3DEC** provides staged gravity, load, and prescribed-displacement analyses
through `compas_3dec` and a licensed external Itasca 3DEC installation. Install
the optional Python adapter with `pip install -e ".[threedec]"`. The executable
is discovered automatically, or its path and run workspace can be set in
`CM_Problem_setsolver`.

CRA and RBE exclude support blocks from the equilibrium system, so they have no
displacement degrees of freedom and refuse a problem carrying a prescribed
displacement. Use LMGC90 or 3DEC for those problems.

## User Interface

COMPAS-Masonry defines 28 Rhino commands, all prefixed `CM_` and grouped by the
stage they belong to:

| Group | Commands |
|---|---|
| **Session** | `CM_Masonry_start`, `CM_Session_undo`, `CM_Session_redo`, `CM_Session_import`, `CM_Session_save`, `CM_Session_redraw`, `CM_Session_clear`, `CM_Session_settings` |
| **Model** | `CM_Model_blocks`, `CM_Model_contacts`, `CM_Model_supports`, `CM_Model_material`, `CM_Model_materialassign` |
| **Problem** | `CM_Problem_create`, `CM_Problem_contactlaw`, `CM_Problem_setsolver`, `CM_Problem_loads`, `CM_Problem_displacements`, `CM_Problem_solve` |
| **Results** | `CM_Results_show`, `CM_Results_print`, `CM_Results_block` |
| **TNA** | `CM_TNA_envelope`, `CM_TNA_formdiagram`, `CM_TNA_supports`, `CM_TNA_loads`, `CM_TNA_analysis`, `CM_TNA_blockexport` |

A typical run goes left to right through those groups: build the model, compute
its contacts, mark supports, assign a material, create a problem with a contact
law and a solver, add loads, solve, and draw the results.

**A problem is the load case.** Loads and prescribed movements are added straight
to a problem; solving applies all of them. To compare two load cases, duplicate
the problem in `CM_Problem_create`.

Saving works the way RhinoVAULT's does: `CM_Session_save` writes the whole
session to one JSON file and `CM_Session_import` opens it. There are no
per-artefact import/export commands. Results are left out deliberately — they are
re-derived by `CM_Problem_solve`.

These commands can be executed using the Rhino command line (simply start typing the command name),
or with the corresponding buttons of the COMPAS-Masonry toolbar.

![COMPAS-Masonry toolbar](/gitbook/.gitbook/assets/COMPAS-Masonry_toolbar.png)

If the toolbar is not visible after installing COMPAS-Masonry,
you can load it from the "Toolbars" page.
To open the "Toolbars" page, type `Toolbar` on the Rhino command line...

![Rhino Toolbars](/gitbook/.gitbook/assets/Rhino_toolbars.png)

## Documentation

For further "getting started" instructions, a tutorial, examples, and an detailed description of the individual commands and the user interface, please check out the online documentation here: [COMPAS-Masonry Gitbook](https://blockresearchgroup.gitbook.io/COMPAS-Masonry)

## Issues

Please report problems using the issue tracker of the github repo: <https://github.com/blockresearchgroup/compas-Masonry/issues>
