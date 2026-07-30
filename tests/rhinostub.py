"""Minimal stand-ins for the Rhino/.NET modules, so command modules import headlessly.

`compas_masonry.inputs` touches `Rhino.Input.Custom.OptionDouble` at class
definition time, and every command imports `rhinoscriptsyntax`, so a command
module cannot be imported outside Rhino at all without this. That blocks
testing even the pure logic inside those modules — face-index parsing, keyword
sanitizing, the BC-kind matrix.

`install()` registers just enough for import. Nothing here emulates Rhino
behaviour: anything that actually draws or prompts must not be called.
"""

import sys
import types


class _Option:
    """Stands in for OptionDouble / OptionInteger / OptionToggle.

    Keeps CurrentValue, since `inputs.Options.values` reads it back and the
    Eto renderer writes it.
    """

    def __init__(self, value=None, *args, **kwargs):
        self.CurrentValue = value


def install() -> None:
    """Register the stub modules in `sys.modules` (idempotent)."""
    if "rhinoscriptsyntax" in sys.modules and getattr(sys.modules["rhinoscriptsyntax"], "_compas_masonry_stub", False):
        return

    rhino = types.ModuleType("Rhino")
    rhino.Input = types.SimpleNamespace(
        Custom=types.SimpleNamespace(
            OptionDouble=_Option,
            OptionInteger=_Option,
            OptionToggle=_Option,
            GetOption=object,
        ),
        GetResult=types.SimpleNamespace(Option="Option", Nothing="Nothing", Cancel="Cancel"),
        RhinoGet=types.SimpleNamespace(GetString=lambda *a, **k: (None, "")),
    )
    rhino.Commands = types.SimpleNamespace(Result=types.SimpleNamespace(Success="Success"))
    rhino.DocObjects = types.SimpleNamespace(ObjectAttributes=object, Material=object)
    rhino.Geometry = types.SimpleNamespace()
    rhino.Render = types.SimpleNamespace()

    system = types.ModuleType("System")
    system.Exception = Exception
    drawing = types.ModuleType("System.Drawing")
    drawing.Color = types.SimpleNamespace(FromArgb=lambda *a: None)
    system.Drawing = drawing

    feedback = types.ModuleType("compas_rui.feedback")
    feedback.warn = lambda *a, **k: None
    feedback.confirm = lambda *a, **k: True
    feedback.displaywarning = lambda *a, **k: None

    rs = types.ModuleType("rhinoscriptsyntax")
    rs._compas_masonry_stub = True

    modules = {
        "Rhino": rhino,
        "System": system,
        "System.Drawing": drawing,
        "rhinoscriptsyntax": rs,
        "scriptcontext": types.ModuleType("scriptcontext"),
        "compas_rhino": types.ModuleType("compas_rhino"),
        "compas_rhino.objects": types.ModuleType("compas_rhino.objects"),
        "compas_rhino.layers": types.ModuleType("compas_rhino.layers"),
        "compas_rhino.conversions": types.ModuleType("compas_rhino.conversions"),
        "compas_rui": types.ModuleType("compas_rui"),
        "compas_rui.feedback": feedback,
    }
    for name, module in modules.items():
        sys.modules[name] = module


def command_path(stem, commands=None):
    """Find `commands/CM_<stem>.py`, tolerating a suffix such as `_options`.

    Command files get renamed (the `_options` suffix was dropped once the
    frozen originals were deleted), and a test that hard-codes a filename fails
    for a reason that has nothing to do with what it tests.
    """
    import pathlib

    commands = pathlib.Path(commands or pathlib.Path(__file__).resolve().parents[1] / "commands")
    exact = commands / f"CM_{stem}.py"
    if exact.exists():
        return exact

    matches = sorted(commands.glob(f"CM_{stem}*.py"))
    if not matches:
        raise FileNotFoundError(f"No command file for '{stem}' in {commands}")
    return matches[0]


def load_command(path, name="command"):
    """Import a `commands/CM_*.py` module by path or stem, with the stubs installed."""
    import importlib.util
    import pathlib

    install()
    path = pathlib.Path(path)
    if not path.exists():
        path = command_path(str(path))

    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
