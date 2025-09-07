#! python3
# venv: brg-csd
# r: compas_masonry

import rhinoscriptsyntax as rs  # type: ignore

from compas_masonry.forms.settings import SettingsForm
from compas_masonry.session import MasonrySession as Session

# =============================================================================
# Command
# =============================================================================


def RunCommand():
    session = Session()

    options = ["Masonry", "FormDiagram", "Envelope", "TNA"]

    option = rs.GetString(message="Choose a settings section, or escape/cancel to exit.", strings=options)
    if not option:
        return

    if option == "Masonry":
        form = SettingsForm(session.settings, title=option)
        form.show()

    elif option == "FormDiagram":
        form = SettingsForm(session.settings.formdiagram, title=option)
        form.show()

    elif option == "Envelope":
        form = SettingsForm(session.settings.tna, title=option)
        form.show()

    elif option == "TNA":
        form = SettingsForm(session.settings.tna, title=option)
        form.show()

    else:
        raise NotImplementedError

    show_intrados = session.settings.envelope.show_intrados
    show_middle = session.settings.envelope.show_middle
    show_extrados = session.settings.envelope.show_extrados

    intradosobj = session.scene.find_by_name("Intrados")
    if intradosobj:
        intradosobj.show = show_intrados

    middleobj = session.scene.find_by_name("Middle")
    if middleobj:
        middleobj.show = show_middle

    extradosobj = session.scene.find_by_name("Extrados")
    if extradosobj:
        extradosobj.show = show_extrados

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
