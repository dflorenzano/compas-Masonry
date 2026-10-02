# Getting Started

COMPAS Masonry is a plugin for Rhino 8 and uses the new CPython runtime.
It can be installed using Yak, Rhino's package manager. This page will guide you through the installation process.

***

## Requirements

* [Rhino 8](https://www.rhino3d.com/)

{% hint style="warning" %}
**To do:** supported operating systems and versions (RhinoVAULT states Windows 10+ / macOS 12+; confirm ours).
{% endhint %}

{% hint style="warning" %}
COMPAS Masonry is available for Rhino 8 **only.**
{% endhint %}

***

## 1. Installation

1. Start Rhino 8 and launch Yak by typing `PackageManager` in the Rhino command line.
2. Search the online packages for "COMPAS Masonry".
3. Select "COMPAS-Masonry" from the list.
4. Make sure the latest version is selected, then click Install.

{% hint style="warning" %}
**To do:** screenshot of the Package Manager (macOS).
{% endhint %}

***

## 2. COMPAS Masonry Toolbar

After the installation, you should see the COMPAS Masonry toolbar in the Rhino workspace.

{% hint style="warning" %}
**To do:** screenshot of the toolbar (macOS).
{% endhint %}

If the toolbar is not visible, you can load it from the "Toolbars" tab in Rhino options.
To open the "Toolbars" page, type `Toolbars` on the Rhino command line.

***

## 3. Check the Installation

To check the installation, press the left-most button on the toolbar, or run `CM_Masonry_start` in the Rhino command line.

|  |  |  |
| :-: | --- | --- |
| <p align="center"><img src="../.gitbook/assets/icons/CM_Masonry_start.svg" alt="" data-size="original"></p> | <p><strong>Rhino command name</strong></p><p><code>CM_Masonry_start</code></p> | <p><strong>source file</strong></p><p><a href="https://github.com/BlockResearchGroup/compas-Masonry/blob/main/commands/CM_Masonry_start.py"><code>CM_Masonry_start.py</code></a></p> |

This starts a COMPAS Masonry session and shows the splash screen.

The COMPAS packages that COMPAS Masonry needs are installed automatically when a COMPAS Masonry command runs
and they are not yet available. They are installed in a separate virtual environment named `brg-csd`.

{% hint style="info" %}
Installing the packages (and their dependencies) may take some time the first time, so don't worry if nothing appears immediately.
{% endhint %}

{% hint style="warning" %}
**To do:** the repository README says the environment is named `COMPAS-Masonry`, but every command header declares `# venv: brg-csd`. Fix the README.
{% endhint %}
