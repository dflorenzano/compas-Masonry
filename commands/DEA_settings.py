#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import rhinoscriptsyntax as rs  # type: ignore
from pydantic import BaseModel

from compas_masonry.session import MasonrySession as Session
from compas_rui.forms import NamedValuesForm


def update_settings(model, title):
    names = []
    values = []
    for name, info in model.model_fields.items():
        if issubclass(info.annotation, BaseModel):
            continue
        names.append(name)
        values.append(getattr(model, name))
    form = NamedValuesForm(names, values, title=title)
    if form.show():
        for name, value in form.attributes.items():
            setattr(model, name, value)


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    options = ["Masonry", "Model"]

    option = rs.GetString(message="Choose a settings section, or escape/cancel to exit.", strings=options)
    if not option:
        return

    if option == "Masonry":
        update_settings(session.settings, title=option)

    elif option == "Model":
        raise NotImplementedError

    else:
        raise NotImplementedError

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
