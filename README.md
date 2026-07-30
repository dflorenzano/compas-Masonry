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
> These currently need **compas_cra 0.5.0**, which is not on PyPI yet, together
> with **pyomo >= 6.7.3**. The published compas_cra 0.4.0 cannot be used with a
> NumPy 2 environment. Until 0.5.0 is released, this is a manual install step.

**LMGC90** (contact dynamics, and the only solver here that returns
displacements) is not available inside Rhino: `compas_lmgc90` is a compiled
extension and there is no build for Rhino 8's Python 3.9.

## User Interface

COMPAS-Masonry defines 33 Rhino commands, all prefixed `CM_` and grouped by the
stage they belong to:

| Group | Commands |
|---|---|
| **Session** | `CM_Masonry_Start`, `CM_Session_settings`, `CM_Session_redraw`, `CM_Session_undo`, `CM_Session_redo`, `CM_Session_clear`, `CM_Masonry_import`, `CM_Masonry_export` |
| **Model** | `CM_Model_blocks`, `CM_Model_contacts`, `CM_Model_supports`, `CM_Model_material`, `CM_Model_materialassign`, `CM_Model_import`, `CM_Model_export` |
| **Problem** | `CM_Problem_create`, `CM_Problem_contactlaw`, `CM_Problem_solver`, `CM_Problem_createbc`, `CM_Problem_addload`, `CM_Problem_displacements`, `CM_Problem_solve`, `CM_Problem_export` |
| **Results** | `CM_Results_show`, `CM_Results_print`, `CM_Results_blockdata`, `CM_Results_export` |
| **TNA** | `CM_TNA_envelope`, `CM_TNA_formdiagram`, `CM_TNA_supports`, `CM_TNA_loads`, `CM_TNA_analysis`, `CM_TNA_blockexports` |

A typical run goes left to right through those groups: build the model, compute
its contacts, mark supports, assign a material, create a problem with a contact
law and a solver, give it boundary conditions with their loads, solve, and draw
the results.

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
