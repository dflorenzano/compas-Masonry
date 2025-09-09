#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.3


from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session()

    model: BlockModel = session["blockmodel"]
    if model is None:
        warn("No block model in the session.")
        return


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
