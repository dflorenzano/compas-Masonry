# 4b. Print Results

|  |  |  |
| :-: | --- | --- |
| <p align="center"><img src="../../.gitbook/assets/icons/CM_Results_print.svg" alt="" data-size="original"></p> | <p><strong>Rhino command name</strong></p><p><code>CM_Results_print</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Results_print.py"><code>CM_Results_print.py</code></a></p> |

Prints a stored result set in the command window, without drawing anything.

## Sub-commands

| Sub-command | Prints |
| --- | --- |
| Summary | the maximum of every quantity, with the contact, block or support where it occurs, plus the contact count and total force |
| Contacts | one row per contact: resultant, magnitude, stress, opening |
| Blocks | one row per moved block: displacement vector and magnitude (empty for CRA and RBE, which move nothing) |
| Reactions | the total contact force on each support, and their sum |
| All | all of the above |

{% hint style="info" %}
**Under the hood** — reads a [Results](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.problem.Results.html) object (**compas_dem**).
{% endhint %}
