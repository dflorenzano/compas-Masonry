# 1c. Supports

|  |  |  |
| :-: | --- | --- |
| <p align="center"><img src="../../.gitbook/assets/icons/CM_Model_supports.svg" alt="" data-size="original"></p> | <p><strong>Rhino command name</strong></p><p><code>CM_Model_supports</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Model_supports.py"><code>CM_Model_supports.py</code></a></p> |

Defines which blocks are supports.

## Sub-commands

### Add

Select blocks to make them supports.

### Remove

Select supports to turn them back into free blocks.

### Clear

Remove all supports.

{% hint style="info" %}
Supports are copied onto each problem when the problem is created. When you change the supports and problems already exist, the command offers to update them.
{% endhint %}

{% hint style="warning" %}
**To do:** figure; describe how supports are drawn (layer `Masonry::Model::Supports`).
{% endhint %}

{% hint style="info" %}
**Under the hood** — sets `is_support` on the blocks of the [BlockModel](https://blockresearchgroup.github.io/compas_dem/latest/api/generated/compas_dem.models.BlockModel.html) (**compas_dem**).
{% endhint %}
