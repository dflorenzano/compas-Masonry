#! python3
# venv: brg-csd
# r: compas_masonry

import pathlib

import Rhino  # type: ignore
import System  # type: ignore

from compas_masonry.splash import SplashForm
from compas_session.lazyload import LazyLoadSession as Session

pluginfile = Rhino.PlugIns.PlugIn.PathFromId(System.Guid("a6dc4669-0e8e-40ea-8d71-b9b0f4764ec1"))
shared = pathlib.Path(str(pluginfile)).parent / "shared"


def RunCommand():
    session = Session(basedir=pathlib.Path().home() / ".compas_session", name="COMPAS-Masonry")
    print(session.basedir)

    form = SplashForm(title="COMPAS Masonry", url=str(shared / "index.html"))
    form.show()


# =============================================================================
# Run as main
# =============================================================================

if __name__ == "__main__":
    RunCommand()
