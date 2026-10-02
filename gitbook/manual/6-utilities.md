# 6. Utilities

## Undo

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_undo.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_undo</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_undo.py"><code>CM_Session_undo.py</code></a></p> |

Steps one state back through COMPAS Masonry's own history: the model, the problems and their boundary conditions, the results and the settings, and redraws the document from it. History keeps the last 10 states and is stored on disk (`~/.compas_session/COMPAS-Masonry.session/`), so it survives a Rhino restart.

***

## Redo

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_redo.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_redo</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_redo.py"><code>CM_Session_redo.py</code></a></p> |

Steps one state forward. A change made after an undo makes redo unavailable.

{% hint style="danger" %}
`CM_Session_undo` and `CM_Session_redo` are not Rhino's Undo and Redo. Rhino's Undo (Cmd+Z / Ctrl+Z) restores document geometry only, and leaves the drawing and the session disagreeing. If that happens, run `CM_Session_redraw`.

History is global, not per document: undo in a newly opened `.3dm` walks back through whatever was worked on last.
{% endhint %}

***

## Open Session

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_import.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_import</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_import.py"><code>CM_Session_import.py</code></a></p> |

Opens a session saved with `CM_Session_save`. It replaces the current model and problems, so it asks for confirmation first. Files written before 2026-08-07 cannot be opened.

***

## Save Session

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_save.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_save</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_save.py"><code>CM_Session_save.py</code></a></p> |

Saves the whole session to a single JSON file: the model with every problem and its boundary conditions, the active problem and the display settings. Solver results are not included by default; they can be included all at once or selected per problem and solve.

***

## Redraw

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_redraw.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_redraw</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_redraw.py"><code>CM_Session_redraw.py</code></a></p> |

`Redraw` redraws the scene from the session. `Status` reports what the session holds: the problems, what each carries, the stored results and where undo stands.

***

## Clear

|  |  |  |
| --- | --- | --- |
| <img src="../.gitbook/assets/icons/CM_Session_clear.svg" alt="" data-size="original"> | <p><strong>Rhino command name</strong></p><p><code>CM_Session_clear</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Session_clear.py"><code>CM_Session_clear.py</code></a></p> |

Clears the session and removes everything COMPAS Masonry drew: all layers under `Masonry` and all session data.

{% hint style="info" %}
**Under the hood** — the session is a [compas_session Session](https://blockresearchgroup.github.io/compas_session/latest/api/generated/compas_session.session.Session.html).
{% endhint %}
