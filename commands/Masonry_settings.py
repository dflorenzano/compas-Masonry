#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.6

import pathlib

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.forms.settings import SettingsForm
from compas_masonry.session import MasonrySession as Session

# =============================================================================
# Command
# =============================================================================


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    options = ["FormDiagram", "Envelope", "BlockModel"]

    option = rs.GetString(message="Choose a settings section, or escape/cancel to exit.", strings=options)
    if not option:
        return

    if option == "FormDiagram":
        form = SettingsForm(session.settings.formdiagram, title=option)
        form.show()

    elif option == "Envelope":
        form = SettingsForm(session.settings.envelope, title=option)
        form.show()

    elif option == "BlockModel":
        form = SettingsForm(session.settings.blockmodel, title=option)
        form.show()

    else:
        raise NotImplementedError

    show_intrados = session.settings.envelope.show_intrados
    show_middle = session.settings.envelope.show_middle
    show_extrados = session.settings.envelope.show_extrados
    show_fill = session.settings.envelope.show_fill

    intradosobj = session.scene.find_by_name("Intrados")
    if intradosobj:
        intradosobj.show = show_intrados

    middleobj = session.scene.find_by_name("Middle")
    if middleobj:
        middleobj.show = show_middle

    extradosobj = session.scene.find_by_name("Extrados")
    if extradosobj:
        extradosobj.show = show_extrados

    fillobj = session.scene.find_by_name("Fill")
    if fillobj:
        fillobj.show = show_fill

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
