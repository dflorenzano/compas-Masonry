"""Hierarchical selection of stored solver results for session export."""

import Eto.Drawing as drawing  # type: ignore
import Eto.Forms as forms  # type: ignore
import Rhino  # type: ignore


class ResultSelectionForm(forms.Dialog[bool]):
    """Select result runs grouped beneath their owning problems."""

    def __init__(self, stored):
        super().__init__()
        self.Title = "Results to include in session"
        self.ClientSize = drawing.Size(620, 430)
        self.Padding = drawing.Padding(10)
        self.Resizable = True
        self.result = None
        self._run_items = []

        self.tree = forms.TreeGridView()
        self.tree.ShowHeader = True
        include_column = forms.GridColumn()
        include_column.HeaderText = "Include"
        include_column.DataCell = forms.CheckBoxCell(0)
        include_column.Editable = True
        include_column.Width = 70
        self.tree.Columns.Add(include_column)

        run_column = forms.GridColumn()
        run_column.HeaderText = "Problem / solve run"
        run_column.DataCell = forms.TextBoxCell(1)
        run_column.AutoSize = True
        self.tree.Columns.Add(run_column)

        roots = forms.TreeGridItemCollection()
        for problem_name, runs in stored.items():
            parent = forms.TreeGridItem()
            parent.Values = [None, str(problem_name)]
            for result_key in sorted(runs):
                child = forms.TreeGridItem()
                child.Values = [False, str(result_key)]
                parent.Children.Add(child)
                self._run_items.append((child, problem_name, result_key))
            parent.Expanded = True
            roots.Add(parent)
        self.tree.DataStore = roots

        note = forms.Label()
        note.Text = "Select individual solve runs to embed. Problem rows group their runs."
        ok = forms.Button()
        ok.Text = "Save selected"
        cancel = forms.Button()
        cancel.Text = "Cancel"
        ok.Click += self._on_ok
        cancel.Click += self._on_cancel

        buttons = forms.DynamicLayout()
        buttons.Spacing = drawing.Size(8, 0)
        buttons.AddRow(None, cancel, ok)

        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(6, 6)
        layout.AddRow(note)
        layout.AddRow(self.tree)
        layout.AddRow(buttons)
        self.Content = layout
        self.DefaultButton = ok
        self.AbortButton = cancel

    def _selected(self):
        selected = []
        for child, problem_name, result_key in self._run_items:
            if bool(child.Values[0]):
                selected.append((problem_name, result_key))
        return selected

    def _on_ok(self, sender, event):
        selected = self._selected()
        if not selected:
            forms.MessageBox.Show("Select at least one solve run, or cancel and save without results.", self.Title)
            return
        self.result = selected
        self.Close(True)

    def _on_cancel(self, sender, event):
        self.result = None
        self.Close(False)

    def show(self):
        self.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
        return self.result
