#! python3
# venv: brg-csd
# r: compas_masonry >=0.2.0


from compas_dem.models import BlockModel
from compas_masonry.session import MasonrySession as Session
from compas_rui.feedback import warn


def RunCommand():
    session = Session()

    # retrieve existing model from session

    model: BlockModel = session["blockmodel"]
    if model is None:
        return warn("No existing BlockModel in session. Please create one first.")

    # compute contacts
    # ask user for tolerance

    model.compute_contacts(tolerance=tol)

    # redraw the scene


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
