#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.3

from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import confirm


def RunCommand():
    session = Session()

    if not confirm("Redraw the current scene?"):
        return

    session.scene.redraw()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
