from pydantic import BaseModel

from compas_session.settings import Settings


class FormDiagramSettings(BaseModel):
    show_reactions: bool = True
    show_residuals: bool = False
    show_pipes: bool = False
    show_loads: bool = False
    show_selfweight: bool = False

    scale_reactions: float = 0.1
    scale_residuals: float = 1.0
    scale_pipes: float = 0.01
    scale_loads: float = 1.0
    scale_selfweight: float = 1.0

    tol_vectors: float = 1e-3
    tol_pipes: float = 1e-2


class MasonrySettings(Settings):
    autoupdate: bool = False
    autosave: bool = True

    formdiagram: FormDiagramSettings = FormDiagramSettings()
