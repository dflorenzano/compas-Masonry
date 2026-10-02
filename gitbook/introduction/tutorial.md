# Tutorial

In this tutorial we build a simple stone masonry arch as a discrete element model, define a problem for it,
and compute the contact forces needed to establish equilibrium under self-weight.
It is a "quick start" through the main steps of the workflow. Options are left at their defaults; see the [Manual](../manual/workflow-and-ui.md) for details.

{% hint style="warning" %}
**To do:** run the tutorial end to end on macOS, confirm every step and add one screenshot per step. Optionally attach the session file after each step, as in the examples.
{% endhint %}

***

## 1. Model

### 1a. Blocks

From the toolbar, click the Blocks button or type `CM_Model_blocks`, then choose `Arch`.
Accept the defaults (rise 3, span 6, thickness 0.5, depth 0.5, 15 blocks). See [1a. Blocks](../manual/1-model/blocks.md).

### 1b. Contacts

Run `CM_Model_contacts` and accept the default tolerance and minimum contact area. See [1b. Contacts](../manual/1-model/contacts.md).

### 1c. Supports

Run `CM_Model_supports`, choose `Add` and select the two blocks at the springings of the arch. See [1c. Supports](../manual/1-model/supports.md).

### 1d. Materials

Run `CM_Model_material`, choose `Create` and pick a predefined `Stone`.
Then run `CM_Model_materialassign` and assign it to `All` blocks. See [1d. Materials](../manual/1-model/materials.md).

***

## 2. Problem

Run `CM_Problem_create` and choose `New` (the problem is named `Problem_1` by default). See [2a. Create Problem](../manual/2-problem/create.md).

Run `CM_Problem_contactlaw` and accept the default Mohr-Coulomb friction angle. See [2b. Contact Law](../manual/2-problem/contact-law.md).

Run `CM_Problem_setsolver` and select `CRA`. See [2c. Solver](../manual/2-problem/solver.md).

{% hint style="info" %}
CRA solves self-weight equilibrium only, so this problem carries no loads or prescribed displacements.
{% endhint %}

***

## 3. Solve

Run `CM_Problem_solve`. Solving draws nothing: the result is stored in the session. See [3. Solve](../manual/3-solve.md).

***

## 4. Results

Run `CM_Results_show` and choose `Forces` to draw the contact forces.
Run `CM_Results_print` and choose `Summary` to print the maximum values. See [4. Results](../manual/4-results/README.md).
