# Workflow & UI

## COMPAS Masonry workflow

{% hint style="warning" %}
**To do:** workflow diagram (Model → Problem → Solve → Results), as RhinoVAULT shows for TNA.
{% endhint %}

The workflow of COMPAS Masonry has four main steps and two auxiliary steps.

{% stepper %}
{% step %}
### [1. Model](1-model/README.md)

Create the blocks of the structure, compute the contacts between them, define which blocks are supports, and assign materials.
{% endstep %}

{% step %}
### [2. Problem](2-problem/README.md)

Define an analysis problem on the model: its contact law, its solver, and its loads and prescribed displacements. A model can carry several problems; each problem is one load case.
{% endstep %}

{% step %}
### [3. Solve](3-solve.md)

Solve the active problem. The result is stored in the session, next to earlier results; nothing is drawn yet.
{% endstep %}

{% step %}
### [4. Results](4-results/README.md)

Draw the stored results (forces or displaced geometry), print them in the command window, or inspect individual blocks.
{% endstep %}

{% step %}
### [5. Settings](5-settings.md)

Change the display options and the parameters used by the commands.
{% endstep %}

{% step %}
### [6. Utilities](6-utilities.md)

Undo and redo, open and save session files, redraw and clear the scene.
{% endstep %}
{% endstepper %}

***

## COMPAS Masonry UI

The commands of COMPAS Masonry can be accessed in two ways:

* from the Rhino command line;
* from the COMPAS Masonry toolbar.

### Rhino command line

COMPAS Masonry includes the following Rhino commands, which can be executed from the Rhino command prompt (start typing the command name).

| Command | Description |
| --- | --- |
| [`CM_Masonry_start`](../introduction/getting-started.md) | Start a COMPAS-Masonry session |
| [`CM_Session_undo`](6-utilities.md) | Undo |
| [`CM_Session_redo`](6-utilities.md) | Redo |
| [`CM_Session_import`](6-utilities.md) | Open a saved session |
| [`CM_Session_save`](6-utilities.md) | Save the session to JSON |
| [`CM_Session_redraw`](6-utilities.md) | Redraw the scene |
| [`CM_Session_clear`](6-utilities.md) | Clear the session, the scene and every Masonry layer |
| [`CM_Session_settings`](5-settings.md) | Session settings |
| [`CM_Model_blocks`](1-model/blocks.md) | Create a block model |
| [`CM_Model_contacts`](1-model/contacts.md) | Compute the contacts |
| [`CM_Model_supports`](1-model/supports.md) | Define the supports |
| [`CM_Model_material`](1-model/materials.md) | Manage materials (create/modify/remove/clear/duplicate) |
| [`CM_Model_materialassign`](1-model/materials.md) | Assign a material to blocks |
| [`CM_Problem_create`](2-problem/create.md) | Create, duplicate, activate or delete a problem |
| [`CM_Problem_contactlaw`](2-problem/contact-law.md) | Define the contact law and joint model |
| [`CM_Problem_setsolver`](2-problem/solver.md) | Choose and configure the solver |
| [`CM_Problem_loads`](2-problem/loads.md) | Add or remove loads on a problem |
| [`CM_Problem_displacements`](2-problem/displacements.md) | Prescribe displacements and rotations |
| [`CM_Problem_solve`](3-solve.md) | Solve the problem |
| [`CM_Results_show`](4-results/show.md) | Draw the results (forces or displaced geometry) |
| [`CM_Results_print`](4-results/print.md) | Print the results in the command window |
| [`CM_Results_block`](4-results/block.md) | Results for selected blocks |

### Toolbar

All commands are also accessible through the toolbar. From left to right: the start button, the session utilities and settings, then the Model, Problem and Results groups.

{% hint style="warning" %}
**To do:** toolbar screenshot (macOS). Open decision (plan §4.4, Q11): reorder `resources/rui/ui.json` so the toolbar follows the manual numbering (Model, Problem, Results, then Settings and Utilities), as in RhinoVAULT.
{% endhint %}
