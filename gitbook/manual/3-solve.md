# 3. Solve

|  |  |  |
| :-: | --- | --- |
| <p align="center"><img src="../.gitbook/assets/icons/CM_Problem_solve.svg" alt="" data-size="original"></p> | <p><strong>Rhino command name</strong></p><p><code>CM_Problem_solve</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Problem_solve.py"><code>CM_Problem_solve.py</code></a></p> |

Solves the active problem with its solver. Every load and displacement group on the problem is solved; to solve a different set, duplicate the problem.

Solving draws **nothing**. Each solve stores one result set in the session under a key naming the solver and the time it ran (for example `RBE_2026-08-04T15-30-12`), so a re-solve after changing a material or a contact law is kept next to the earlier run. Use [4. Results](4-results/README.md) to draw or print it.

{% hint style="warning" %}
CRA and RBE are refused for a problem with loads or prescribed displacements, because they would silently return a self-weight answer. They also need a material density on every block and a contact law on the problem; the command names what is missing.
{% endhint %}

## 3DEC stages

With 3DEC, each load and displacement group runs as a sequential stage after gravity. The command asks whether to use the current stage order or change it, and how to group consecutive loads.

{% hint style="warning" %}
**To do:** figure; describe the 3DEC stage dialogs.
{% endhint %}

{% hint style="info" %}
**Under the hood** — calls `solve` on the [Problem](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.problem.Problem.html) and stores a [Results](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.problem.Results.html) object (**compas_dem**) in the session.
{% endhint %}
