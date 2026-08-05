"""Command line input for Rhino commands (Rhino.Input.Custom.GetOption).

Why this exists
---------------
COMPAS has no parameter input layer for Rhino. `compas_rhino.objects` covers
object *selection* (select_object, select_mesh, select_lines, ...),
`compas_rhino.ui` covers point picking and file browsing, and `compas_rui.forms`
covers Eto dialogs — but numbers, strings, toggles and enums have always been
delegated to `rhinoscriptsyntax`, which can only ask for them one at a time.

This module fills exactly that hole, and nothing else: it exposes every
parameter of a command at once as a command line option, so the fields are
visible together, can be edited in any order, and Enter accepts the whole set.
Anything already covered upstream is used as is — object selection stays
`compas_rhino.objects`, list dialogs stay `rs.ListBox`, file dialogs stay
`compas_rui.forms.FileForm`.

Two ways to declare the fields::

    # explicit
    options = Options("Arch")
    options.add_number("rise", 3.0, minimum=0.0)
    options.add_integer("n", 50, minimum=3, keyword="Blocks")
    values = options.get()

    # from an existing pydantic model (compas_session settings, ...)
    options = Options.from_model(session.settings.blockmodel)
    values = options.get()
    if values is not None:
        options.apply(session.settings.blockmodel)

`from_model` reads the same `model_fields` metadata as
`compas_masonry.forms.settings.SettingsForm`, so one pydantic model can be
rendered either as an Eto dialog or on the command line.

Fields can be shown conditionally with `visible`, a callable receiving the dict
of current values, which makes dependent parameters (mu vs phi, fill density
only when there is a fill) collapse into a single prompt.

Notes
-----
- Rhino command option keywords must be a single alphanumeric word starting
  with a letter. Keywords are derived from the field name unless given.
- Free text has no native option widget, so `add_text` shows the current value
  in the prompt and opens a sub-prompt when the keyword is picked.
- Long enumerations (materials, tessellation patterns) belong in `rs.ListBox`,
  not on the command line.

"""

import Rhino  # type: ignore

__all__ = [
    "Options",
    "choose",
    "keyword_from",
    "unique_keywords",
    "field_ge",
    "field_le",
    "BACK",
]

# Returned by a getter when the user picks the "Back" option, so a command can
# step back to the previous prompt instead of cancelling. Distinct from None
# (cancel) and from a values dict (accepted).
BACK = "__back__"


def dialog_input_enabled() -> bool:
    """True if commands should ask for their parameters in an Eto dialog.

    Driven by `settings.dialog_input` (Session_settings -> Input). Reads the
    live session singleton if a command has already created one — never
    constructs a session, and never fails: no session means command line.
    """
    try:
        from compas_masonry.session import MasonrySession

        session = MasonrySession._instance
        return bool(session and session.settings.dialog_input)
    except Exception:
        return False


# =============================================================================
# Pydantic field introspection
# =============================================================================


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


# =============================================================================
# Keywords
# =============================================================================


def keyword_from(name: str) -> str:
    """Turn an arbitrary label into a valid Rhino command option keyword.

    Rhino keywords must be a single alphanumeric word starting with a letter.

    """
    parts = []
    for chunk in str(name).replace("-", " ").replace("_", " ").split():
        parts.append(chunk[0].upper() + chunk[1:] if chunk else chunk)
    keyword = "".join(c for c in "".join(parts) if c.isalnum())
    if not keyword:
        keyword = "Value"
    if not keyword[0].isalpha():
        keyword = "N" + keyword
    return keyword


def unique_keywords(labels) -> list:
    """Build a list of unique keywords, one per label, preserving order."""
    keywords = []
    seen = {}
    for label in labels:
        keyword = keyword_from(label)
        if keyword in seen:
            seen[keyword] += 1
            keyword = f"{keyword}{seen[keyword]}"
        else:
            seen[keyword] = 1
        keywords.append(keyword)
    return keywords


# =============================================================================
# Fields
# =============================================================================


class _Field:
    """Base class for a single command line option.

    `units` exists because a Rhino command option renders as `Keyword=Value`
    and nothing else: the `prompt` is only shown once the option is PICKED, so
    units written there are invisible while you are reading the line. The unit
    is therefore carried separately and shown in the prompt legend (command
    line) or appended to the control label (Eto).
    """

    def __init__(self, name, keyword=None, prompt=None, visible=None, units=None):
        self.name = name
        self.keyword = keyword or keyword_from(name)
        self.prompt = prompt
        self.visible = visible
        self.units = units

    def label(self):
        """Human label for this field: the prompt if given, else the keyword."""
        return self.prompt or self.keyword

    @property
    def value(self):
        raise NotImplementedError

    def add_to(self, go) -> int:
        raise NotImplementedError

    def on_selected(self, go) -> bool:
        """Handle the option being picked. Return False to cancel the getter."""
        return True

    def annotation(self):
        """Extra text appended to the prompt (used by fields without a widget)."""
        return None


class _NumberField(_Field):
    """Numeric option, with optional lower/upper limits enforced by Rhino."""

    option_type = None

    def __init__(self, name, value, minimum=None, maximum=None, **kwargs):
        super().__init__(name, **kwargs)
        # kept for the Eto renderer: the limits cannot be read back off the
        # Rhino option object
        self.minimum = minimum
        self.maximum = maximum
        cls = self.option_type
        if minimum is not None and maximum is not None:
            self.option = cls(value, minimum, maximum)
        elif minimum is not None:
            self.option = cls(value, True, minimum)
        elif maximum is not None:
            self.option = cls(value, False, maximum)
        else:
            self.option = cls(value)

    @property
    def value(self):
        return self.option.CurrentValue

    def add_to(self, go) -> int:
        raise NotImplementedError


class _DoubleField(_NumberField):
    option_type = Rhino.Input.Custom.OptionDouble

    def add_to(self, go) -> int:
        if self.prompt:
            return go.AddOptionDouble(self.keyword, self.option, self.prompt)
        return go.AddOptionDouble(self.keyword, self.option)


class _IntegerField(_NumberField):
    option_type = Rhino.Input.Custom.OptionInteger

    def add_to(self, go) -> int:
        if self.prompt:
            return go.AddOptionInteger(self.keyword, self.option, self.prompt)
        return go.AddOptionInteger(self.keyword, self.option)


class _ToggleField(_Field):
    """Two-state option. Returns a bool, or the state label when `text` is True."""

    def __init__(self, name, value, off="No", on="Yes", text=False, **kwargs):
        super().__init__(name, **kwargs)
        self.off = off
        self.on = on
        self.text = text
        self.option = Rhino.Input.Custom.OptionToggle(bool(value), off, on)

    @property
    def value(self):
        if self.text:
            return self.on if self.option.CurrentValue else self.off
        return self.option.CurrentValue

    def add_to(self, go) -> int:
        return go.AddOptionToggle(self.keyword, self.option)


class _ListField(_Field):
    """Option cycling through a fixed set of values (each must be one word)."""

    def __init__(self, name, values, index=0, **kwargs):
        super().__init__(name, **kwargs)
        self.values = list(values)
        self.index = index

    @property
    def value(self):
        return self.values[self.index]

    def add_to(self, go) -> int:
        return go.AddOptionList(self.keyword, self.values, self.index)

    def on_selected(self, go) -> bool:
        self.index = go.Option().CurrentListOptionIndex
        return True


class _TextField(_Field):
    """Free text. No native widget, so picking the keyword opens a sub-prompt."""

    def __init__(self, name, value="", **kwargs):
        super().__init__(name, **kwargs)
        self.text = value

    @property
    def value(self):
        return self.text

    def add_to(self, go) -> int:
        return go.AddOption(self.keyword)

    def on_selected(self, go) -> bool:
        result, text = Rhino.Input.RhinoGet.GetString(self.prompt or self.name, True, self.text)
        if result != Rhino.Commands.Result.Success:
            return True  # keep the previous value, stay in the getter
        self.text = text
        return True

    def annotation(self):
        return f"{self.keyword}={self.text}"


# =============================================================================
# Options getter
# =============================================================================


class Options:
    """Collect several values at once as Rhino command line options.

    Parameters
    ----------
    prompt : str
        Command prompt shown while the options are displayed.
    accept : str, optional
        Text appended to the prompt to explain how to accept.
    back : bool, optional
        Add a "Back" option. When picked, `get` returns `BACK` instead of a
        values dict, so the command can re-show the previous prompt.

    Examples
    --------
    >>> options = Options("Contact model")
    >>> options.add_toggle("friction", False, off="Phi", on="Mu", text=True)
    >>> options.add_number("phi", 35.0, minimum=0.0, maximum=90.0, visible=lambda v: v["friction"] == "Phi")
    >>> options.add_number("mu", 0.7, minimum=0.0, visible=lambda v: v["friction"] == "Mu")
    >>> values = options.get()

    """

    def __init__(self, prompt="Options", accept="press Enter to accept", back=False):
        self.prompt = prompt
        self.accept = accept
        self.back = back
        self.fields = []

    # -------------------------------------------------------------------------
    # Field declaration
    # -------------------------------------------------------------------------

    def add_number(self, name, value, minimum=None, maximum=None, **kwargs):
        """Add a float option, optionally clamped to [minimum, maximum]."""
        self.fields.append(_DoubleField(name, value, minimum, maximum, **kwargs))
        return self

    def add_integer(self, name, value, minimum=None, maximum=None, **kwargs):
        """Add an int option, optionally clamped to [minimum, maximum]."""
        self.fields.append(_IntegerField(name, value, minimum, maximum, **kwargs))
        return self

    def add_toggle(self, name, value=False, off="No", on="Yes", text=False, **kwargs):
        """Add a two-state option."""
        self.fields.append(_ToggleField(name, value, off=off, on=on, text=text, **kwargs))
        return self

    def add_list(self, name, values, index=0, **kwargs):
        """Add an option cycling through `values` (single words only)."""
        self.fields.append(_ListField(name, values, index=index, **kwargs))
        return self

    def add_text(self, name, value="", **kwargs):
        """Add a free text option (sub-prompt on selection)."""
        self.fields.append(_TextField(name, value, **kwargs))
        return self

    # -------------------------------------------------------------------------
    # Pydantic models
    # -------------------------------------------------------------------------

    @classmethod
    def from_model(cls, model, prompt=None, include=None, exclude=None):
        """Build the options from the fields of a pydantic model.

        Reads the same metadata as `compas_masonry.forms.settings.SettingsForm`
        (title, default, ge/le constraints), so the same model can be rendered
        as an Eto dialog or on the command line.

        Parameters
        ----------
        model : pydantic.BaseModel
            The model instance whose current values seed the options.
        prompt : str, optional
            Command prompt. Defaults to the model class name.
        include : list[str], optional
            Only these field names.
        exclude : list[str], optional
            Skip these field names.

        Returns
        -------
        Options

        Notes
        -----
        Nested models and types without a command line widget (colors, tuples,
        lists) are skipped; edit those in the Eto form.

        """
        from pydantic import BaseModel

        options = cls(prompt or type(model).__name__)

        selected = []
        for name, field in type(model).model_fields.items():
            if include is not None and name not in include:
                continue
            if exclude is not None and name in exclude:
                continue
            annotation = field.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                continue
            if annotation not in (bool, int, float, str):
                continue
            selected.append((name, field))

        keywords = unique_keywords(field.title or name for name, field in selected)

        for (name, field), keyword in zip(selected, keywords):
            annotation = field.annotation
            title = field.title or name.replace("_", " ").capitalize()
            value = getattr(model, name, field.default)

            if annotation is bool:
                options.add_toggle(name, bool(value), keyword=keyword, prompt=title)
            elif annotation is int:
                options.add_integer(name, int(value or 0), minimum=field_ge(field), maximum=field_le(field), keyword=keyword, prompt=title)
            elif annotation is float:
                options.add_number(name, float(value or 0.0), minimum=field_ge(field), maximum=field_le(field), keyword=keyword, prompt=title)
            else:
                options.add_text(name, str(value or ""), keyword=keyword, prompt=title)

        return options

    def apply(self, model, values=None):
        """Write the accepted values back onto a model (or any object).

        Raises whatever the model raises on assignment (pydantic validation
        errors included), so the caller can report them.
        """
        for key, value in (self.values if values is None else values).items():
            setattr(model, key, value)
        return model

    # -------------------------------------------------------------------------
    # Values
    # -------------------------------------------------------------------------

    @property
    def values(self) -> dict:
        """Current value of every field, keyed by field name."""
        return {field.name: field.value for field in self.fields}

    def visible_fields(self, values) -> list:
        return [f for f in self.fields if f.visible is None or f.visible(values)]

    # -------------------------------------------------------------------------
    # Get
    # -------------------------------------------------------------------------

    def get(self, dialog=None):
        """Show all options and wait for the user to accept or cancel.

        Parameters
        ----------
        dialog : bool, optional
            Render as an Eto dialog instead of command line options. Defaults
            to `settings.dialog_input` (Session_settings -> Input), so a
            command never has to care which renderer is in use.

        Returns
        -------
        dict or str or None
            The field values keyed by field name, `BACK` if the user picked the
            Back option, or None if cancelled.

        """
        if dialog is None:
            dialog = dialog_input_enabled()

        if dialog:
            from compas_masonry.forms.options import OptionsForm

            return OptionsForm(self).show()

        go = Rhino.Input.Custom.GetOption()
        go.AcceptNothing(True)

        while True:
            values = self.values
            fields = self.visible_fields(values)

            # options are rebuilt every pass so that `visible` can hide fields;
            # the option objects themselves are reused, so values are kept.
            go.ClearCommandOptions()
            index_field = {}
            for field in fields:
                index_field[field.add_to(go)] = field
            back_index = go.AddOption("Back") if self.back else None

            # One separator style for the whole line. It used to mix "[…]",
            # "(…)" and an em dash in one prompt, which ran together into an
            # unreadable line — and the em dash is not ASCII, so Rhino's command
            # line renders it inconsistently. Segments joined by " | ", units as
            # "Keyword [unit]", ASCII throughout.
            segments = [self.prompt]

            annotations = [a for a in (f.annotation() for f in fields) if a]
            if annotations:
                segments.append(", ".join(annotations))

            # units of the CURRENTLY VISIBLE fields, since `visible` predicates
            # swap whole parameter sets in and out between passes
            units = ", ".join(f"{f.keyword} [{f.units}]" for f in fields if f.units)
            if units:
                segments.append(units)

            if self.accept:
                segments.append(self.accept)

            go.SetCommandPrompt(" | ".join(segments))

            result = go.Get()

            if result == Rhino.Input.GetResult.Option:
                if back_index is not None and go.OptionIndex() == back_index:
                    return BACK
                field = index_field.get(go.OptionIndex())
                if field is not None and not field.on_selected(go):
                    return None
                continue

            if result == Rhino.Input.GetResult.Nothing:
                return self.values

            return None


# =============================================================================
# One-shot helper
# =============================================================================


BACK_LABEL = "< Back"


def choose(prompt, options, default=None, back=False, dialog=None):
    """Pick one item from a short list, shown as command line keywords.

    For long enumerations use `rs.ListBox` instead.

    Parameters
    ----------
    prompt : str
        Command prompt.
    options : list[str]
        Labels to choose from. Labels that are not valid Rhino keywords are
        sanitized for display, but the original label is returned.
    default : str, optional
        Label returned when the user presses Enter.
    back : bool, optional
        Add a "Back" option, returned as `BACK`.
    dialog : bool, optional
        Ask in a list dialog instead of on the command line. Defaults to
        `settings.dialog_input`.

    Returns
    -------
    str or None
        The chosen label, `BACK`, or None if cancelled.

    """
    options = list(options)
    if not options:
        return None

    if dialog is None:
        dialog = dialog_input_enabled()

    if dialog:
        import rhinoscriptsyntax as rs  # type: ignore

        labels = options + ([BACK_LABEL] if back else [])
        picked = rs.ListBox(labels, message=prompt, title="COMPAS Masonry", default=default)
        if not picked:
            return None
        return BACK if picked == BACK_LABEL else picked

    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt(f"{prompt} <{default}>" if default else prompt)
    if default is not None:
        go.AcceptNothing(True)

    index_label = {}
    for keyword, label in zip(unique_keywords(options), options):
        index_label[go.AddOption(keyword)] = label
    back_index = go.AddOption("Back") if back else None

    result = go.Get()
    if result == Rhino.Input.GetResult.Option:
        if back_index is not None and go.OptionIndex() == back_index:
            return BACK
        return index_label.get(go.OptionIndex())
    if result == Rhino.Input.GetResult.Nothing:
        return default
    return None
