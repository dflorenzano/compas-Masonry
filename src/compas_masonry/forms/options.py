#! python3
# venv: brg-csd
# r: compas_masonry

"""Eto renderer for `compas_masonry.inputs.Options`.

The second renderer of one declaration. A command declares its parameters once::

    options = Options("Contact law")
    options.add_toggle("friction", False, off="Phi", on="Mu", text=True)
    options.add_number("phi", 35.0, minimum=0.0, maximum=90.0, visible=lambda v: v["friction"] == "Phi")
    values = options.get()

and `Options.get()` sends it either to the command line (Rhino.Input.Custom) or
here, depending on `settings.dialog_input`. The command does not change.

Why this exists: on macOS, Rhino draws command line options in a floating
"command options dialog" that always carries an empty text entry box (Rhino's
own chrome — there is no `GetOption` API to remove it). Users who keep that
dialog on can switch the whole plugin to real forms instead.

The form writes back into the same Rhino option objects the command line
renderer uses (`OptionDouble.CurrentValue`, `_ListField.index`, ...), so
`Options.values` behaves identically whichever renderer ran.
"""

import Eto.Drawing as drawing  # type: ignore
import Eto.Forms as forms  # type: ignore
import Rhino  # type: ignore
import Rhino.UI  # type: ignore

from compas_masonry.inputs import BACK
from compas_masonry.inputs import _DoubleField
from compas_masonry.inputs import _IntegerField
from compas_masonry.inputs import _ListField
from compas_masonry.inputs import _TextField
from compas_masonry.inputs import _ToggleField


class OptionsForm(forms.Dialog[bool]):
    """Render an `Options` declaration as a modal Eto dialog.

    Parameters
    ----------
    options : :class:`compas_masonry.inputs.Options`
        The declaration to render. Its fields are mutated in place on OK.
    width : int, optional

    """

    def __init__(self, options, width: int = 420):
        super().__init__()

        self.options = options
        self.controls = {}
        self.rows = {}
        self.result = None

        self.Title = options.prompt
        self.ClientSize = drawing.Size(width, -1)
        self.Padding = drawing.Padding(0)

        self.Content = self._build_layout(width)
        self._refresh_visibility()

        self.DefaultButton = self.ok_button
        self.AbortButton = self.cancel_button

    # =============================================================================
    # Layout
    # =============================================================================

    def _build_layout(self, width):
        layout = forms.DynamicLayout()
        layout.Padding = drawing.Padding(12)
        layout.Spacing = drawing.Size(8, 8)

        # one panel per field, so hiding a field also removes its label and its
        # vertical space (a TableLayout row would leave a gap behind)
        stack = forms.StackLayout()
        stack.Orientation = forms.Orientation.Vertical
        stack.HorizontalContentAlignment = forms.HorizontalAlignment.Stretch
        stack.Spacing = 6

        for field in self.options.fields:
            control = self._create_control(field)
            self.controls[field.name] = control

            label = forms.Label()
            text = field.prompt or field.name.replace("_", " ").capitalize()
            # units are carried separately (the command line has nowhere to show
            # them but the prompt); here there is room on the label itself
            units = getattr(field, "units", None)
            label.Text = f"{text} [{units}]" if units and units not in text else text

            row = forms.DynamicLayout()
            row.Spacing = drawing.Size(8, 2)
            row.AddRow(label)
            row.AddRow(control)

            panel = forms.Panel()
            panel.Content = row
            self.rows[field.name] = panel

            stack.Items.Add(forms.StackLayoutItem(panel, True))

        layout.AddRow(stack)
        layout.AddRow(None)

        self.ok_button = forms.Button()
        self.ok_button.Text = "OK"
        self.ok_button.Click += self._on_ok

        self.cancel_button = forms.Button()
        self.cancel_button.Text = "Cancel"
        self.cancel_button.Click += self._on_cancel

        if self.options.back:
            self.back_button = forms.Button()
            self.back_button.Text = "Back"
            self.back_button.Click += self._on_back
            layout.AddRow(self.back_button, None, self.ok_button, self.cancel_button)
        else:
            layout.AddRow(None, self.ok_button, self.cancel_button)

        return layout

    def _create_control(self, field):
        """Build the control matching a field, seeded with its current value."""
        if isinstance(field, (_DoubleField, _IntegerField)):
            control = forms.NumericUpDown()
            control.Value = float(field.value)
            control.DecimalPlaces = 0 if isinstance(field, _IntegerField) else 3
            control.Increment = 1 if isinstance(field, _IntegerField) else 0.1
            if field.minimum is not None:
                control.MinValue = field.minimum
            if field.maximum is not None:
                control.MaxValue = field.maximum
            control.ValueChanged += self._on_changed

        elif isinstance(field, _ToggleField):
            if field.text:
                # a text toggle is a two-state choice, clearer as a dropdown
                control = forms.DropDown()
                control.DataStore = [field.off, field.on]
                control.SelectedIndex = 1 if field.option.CurrentValue else 0
                control.SelectedIndexChanged += self._on_changed
            else:
                control = forms.CheckBox()
                control.Text = field.on if field.on != "Yes" else ""
                control.Checked = bool(field.option.CurrentValue)
                control.CheckedChanged += self._on_changed

        elif isinstance(field, _ListField):
            control = forms.DropDown()
            control.DataStore = list(field.values)
            control.SelectedIndex = field.index
            control.SelectedIndexChanged += self._on_changed

        else:  # _TextField
            control = forms.TextBox()
            control.Text = field.value or ""
            control.TextChanged += self._on_changed

        return control

    # =============================================================================
    # Conditional fields
    # =============================================================================

    def _current_values(self) -> dict:
        """Field values as they stand in the controls, for `visible` predicates."""
        values = {}
        for field in self.options.fields:
            control = self.controls[field.name]

            if isinstance(field, _IntegerField):
                values[field.name] = int(control.Value)
            elif isinstance(field, _DoubleField):
                values[field.name] = float(control.Value)
            elif isinstance(field, _ToggleField):
                if field.text:
                    values[field.name] = field.on if control.SelectedIndex == 1 else field.off
                else:
                    values[field.name] = bool(control.Checked)
            elif isinstance(field, _ListField):
                values[field.name] = field.values[control.SelectedIndex]
            else:
                values[field.name] = control.Text

        return values

    def _refresh_visibility(self):
        """Show/hide fields according to their `visible` predicate.

        The command line renderer rebuilds the option list on every pass; the
        same idea, applied to panel visibility.
        """
        values = self._current_values()
        for field in self.options.fields:
            self.rows[field.name].Visible = field.visible is None or field.visible(values)

    def _on_changed(self, sender, e):
        try:
            self._refresh_visibility()
        except Exception as ex:  # a bad predicate must not break the dialog
            print(f"Could not update the visible options: {ex}")

    # =============================================================================
    # Result
    # =============================================================================

    def _apply(self):
        """Write the control values back into the Rhino option objects.

        Keeping the option objects as the single source of truth is what makes
        `Options.values` identical whichever renderer ran.
        """
        for field in self.options.fields:
            control = self.controls[field.name]

            if isinstance(field, _IntegerField):
                field.option.CurrentValue = int(control.Value)
            elif isinstance(field, _DoubleField):
                field.option.CurrentValue = float(control.Value)
            elif isinstance(field, _ToggleField):
                field.option.CurrentValue = control.SelectedIndex == 1 if field.text else bool(control.Checked)
            elif isinstance(field, _ListField):
                field.index = control.SelectedIndex
            else:
                field.text = control.Text

    def _on_ok(self, sender, e):
        try:
            self._apply()
        except Exception as ex:
            forms.MessageBox.Show(str(ex), "Invalid input")
            return
        self.result = self.options.values
        self.Close(True)

    def _on_cancel(self, sender, e):
        self.result = None
        self.Close(False)

    def _on_back(self, sender, e):
        self.result = BACK
        self.Close(False)

    def show(self):
        """Show the dialog modally.

        Returns
        -------
        dict or str or None
            The field values, `BACK`, or None if cancelled — the same contract
            as the command line `Options.get()`.

        """
        self.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
        return self.result
