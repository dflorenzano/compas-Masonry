# 5. Settings

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_settings.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_settings</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_settings.py"><code>CM_Session_settings.py</code></a></p> |

Under Settings, the global parameters of COMPAS Masonry and the display options can be changed. Choose a section, then edit it in a `Dialog` or on the `CommandLine`.

## Categories

### General

| Setting | Title | Default |
| --- | --- | --- |
| `autoupdate` | Auto Update | True |
| `autosave` | Auto Save | False |
| `dialog_input` | Use Dialogs For Command Input | False |

`dialog_input` decides how every other command asks for its parameters: command line options (default) or a dialog with the same fields.

### Block model

| Setting | Title | Default |
| --- | --- | --- |
| `show_blocks` | Show Blocks | True |
| `show_supports` | Show Supports | True |
| `show_contacts` | Show Contacts | False |
| `show_interactions` | Show Interactions | False |
| `show_resultants` | Show Contact Resultants | True |
| `show_reactions` | Show Reactions | True |
| `show_normalforces` | Show Normal Forces | False |
| `show_frictionforces` | Show Friction Forces | False |
| `show_horizontalforces` | Show Horizontal Forces | False |
| `show_verticalforces` | Show Vertical Forces | False |
| `show_selfweight` | Show Selfweight | False |
| `show_cornerforces` | Show Corner Forces | False |
| `pickmode_face` | Display Mode While Picking Faces | Shaded |
| `pickmode_vertex` | Display Mode While Picking Vertices | Wireframe |
| `results_display_mode` | Display Mode When Showing Results | Wireframe |
| `scale_selfweight` | Scale Selfweight (relative) | 1.0 |
| `scale_gravity` | Scale Gravity (m per m/s2) | 0.1 |
| `scale_displacement_arrows` | Scale Displacement Arrows (relative) | 1.0 |
| `scale_displacement` | Scale Result Displacements | 1.0 |
| `scale_forces` | Scale Result Forces (relative) | 1.0 |
| `contact_tolerance` | Contact Tolerance | 1e-3 |
| `contact_minimum_area` | Contact Minimum Area | 1e-2 |

{% hint style="warning" %}
**To do:** one-line meaning per setting (the code comments in `src/compas_masonry/settings.py` explain most of them). The `formdiagram` and `envelope` sections belong to TNA, which is out of scope for this release: hide them or remove them from the settings.
{% endhint %}

{% hint style="info" %}
**Under the hood** — settings are a pydantic model stored in the session ([compas_session](https://blockresearchgroup.github.io/compas_session/latest/api/generated/compas_session.session.Session.html)).
{% endhint %}
