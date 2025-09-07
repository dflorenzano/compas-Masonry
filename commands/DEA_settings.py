#! python3
# venv: brg-csd
# r: compas_masonry

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


# =============================================================================
# Command
# =============================================================================


def RunCommand():
    session = Session()

    options = ["Masonry", "BlockModel", "DEA"]

    option = rs.GetString(message="Choose a settings section, or escape/cancel to exit.", strings=options)
    if not option:
        return

    if option == "Masonry":
        update_settings(session.settings, title=option)

    elif option == "BlockModel":
        update_settings(session.settings.blockmodel, title=option)

    elif option == "DEA":
        update_settings(session.settings.dea, title=option)

    else:
        raise NotImplementedError

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
