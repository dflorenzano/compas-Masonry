#! python3
# venv: brg-csd
# r: compas_masonry

from typing import Union

import Eto.Drawing as drawing  # type: ignore
import Eto.Forms as forms  # type: ignore
import Rhino  # type: ignore
import Rhino.UI  # type: ignore
from pydantic import BaseModel
from pydantic import Field

from compas.colors import Color
from compas_session.settings import Settings


def field_ge(field):
    """Get the 'greater than or equal to' constraint from a Pydantic field.

    Parameters
    ----------
    field : ModelField
        The Pydantic model field.

    Returns
    -------
    float or int or None
        The 'greater than or equal to' constraint if it exists, otherwise None.

    """
    ge = None
    for m in field.metadata:
        if hasattr(m, "ge"):
            ge = m.ge
            break
    return ge


def field_le(field):
    """Get the 'less than or equal to' constraint from a Pydantic field.

    Parameters
    ----------
    field : ModelField
        The Pydantic model field.

    Returns
    -------
    float or int or None
        The 'less than or equal to' constraint if it exists, otherwise None.

    """
    le = None
    for m in field.metadata:
        if hasattr(m, "le"):
            le = m.le
            break
    return le


class SettingsForm(forms.Dialog[bool]):
    """A dynamic form for editing Pydantic models.

    Parameters
    ----------
    model_cls : Type[BaseModel]
        The Pydantic model class to create the form for.
    width : int, optional
        The width of the form, by default 400.

    """

    def __init__(self, model: Union[Settings, BaseModel], title: str = "Settings", width: int = 400):
        super().__init__()
        self.ClientSize = drawing.Size(width, -1)
        self.model = model
        self.model_cls = type(model)
        self.controls = {}
        self.Title = title

        self.Content = self._build_layout()

        self.DefaultButton = self.ok_button
        self.AbortButton = self.cancel_button

    def _build_layout(self):
        layout = forms.DynamicLayout()
        layout.Padding = drawing.Padding(10)
        layout.Spacing = drawing.Size(10, 10)

        for name, field in self.model_cls.model_fields.items():
            if issubclass(field.annotation, BaseModel):  # type: ignore
                continue

            text = field.title or name.replace("_", " ").capitalize()
            label = forms.Label()
            label.Text = text
            control = self._create_control(name, field, field.default)
            self.controls[name] = control
            layout.AddRow(label, control)

        layout.AddRow(None)

        self.ok_button = forms.Button()
        self.ok_button.Text = "OK"
        self.ok_button.Click += self._on_ok

        self.cancel_button = forms.Button()
        self.cancel_button.Text = "Cancel"
        self.cancel_button.Click += self._on_cancel

        layout.AddRow(None, self.ok_button, self.cancel_button)
        return layout

    def _create_control(self, name, field, default):
        if field.annotation is str:
            value = getattr(self.model, name, default) or ""
            control = forms.TextBox()
            control.Text = value

        elif field.annotation is int:
            value = getattr(self.model, name, default) or 0
            control = forms.NumericUpDown()
            control.Value = value
            control.MinValue = field_ge(field)
            control.MaxValue = field_le(field)

        elif field.annotation is float:
            value = getattr(self.model, name, default) or 0.0
            control = forms.NumericUpDown()
            control.Value = value
            control.DecimalPlaces = 3
            control.MinValue = field_ge(field)
            control.MaxValue = field_le(field)

        elif field.annotation is bool:
            value = getattr(self.model, name, default) or False
            control = forms.CheckBox()
            control.Checked = value

        elif (
            field.annotation is tuple
            and hasattr(field, "default")
            and isinstance(field.default, tuple)
            and len(field.default) == 4
            and all(isinstance(x, int) for x in field.default)
        ):
            value = getattr(self.model, name, default) or (255, 255, 255, 255)
            color = drawing.Color.FromArgb(*value)
            control = forms.ColorPicker()
            control.Value = color

        else:
            value = getattr(self.model, name, default) or ""
            control = forms.TextBox()
            control.Text = str(value)

        return control

    def _on_ok(self, sender, e):
        values = {}
        for name, control in self.controls.items():
            if isinstance(control, forms.TextBox):
                values[name] = control.Text
            elif isinstance(control, forms.NumericUpDown):
                values[name] = control.Value
            elif isinstance(control, forms.CheckBox):
                values[name] = control.Checked
            elif isinstance(control, forms.ColorPicker):
                c = control.Value
                values[name] = (c.R, c.G, c.B, c.A)
        try:
            for key, value in values.items():
                setattr(self.model, key, value)
            self.Close(True)
        except Exception as ex:
            forms.MessageBox.Show(str(ex), "Validation Error")

    def _on_cancel(self, sender, e):
        self.Close(False)

    def show(self):
        return self.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":

    class TestSettings(BaseModel):
        name: str = Field("Default", title="Name", description="Enter your name")
        age: int = Field(30, title="Age", ge=0, le=120)
        is_active: bool = Field(True, title="Active")
        color: tuple = Field(Color.white().rgba255, title="Color", description="Pick a color")

    settings = TestSettings(name="Alice", age=28, is_active=True, color=Color.red().rgba255)
    dialog = SettingsForm(settings)  # type: ignore

    if dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow):
        print(dialog.model)
