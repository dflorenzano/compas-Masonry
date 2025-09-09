#! python3
# venv: brg-csd
# r: compas_masonry>=0.2.4

# import pathlib

# from compas_dem.models import BlockModel
# from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    # session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")

    # model: BlockModel = session["blockmodel"]
    # if model is None:
    #     warn("No block model in the session.")
    #     return

    warn("Not available yet.")


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
