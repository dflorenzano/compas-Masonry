from pydantic import BaseModel
from pydantic import Field

from compas_session.settings import Settings


class FormDiagramSettings(BaseModel):
    show_reactions: bool = Field(default=True, title="Show Reactions")
    show_pipes: bool = Field(default=False, title="Show Pipes")
    show_loads: bool = Field(default=False, title="Show Loads")
    show_bounds: bool = Field(default=False, title="Show Bounds")
    show_cracks: bool = Field(default=False, title="Show Cracks")

    scale_reactions: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Reactions")
    scale_pipes: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Pipes")
    scale_loads: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Loads")

    tol_vectors: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Tolerance Vectors")
    tol_pipes: float = Field(default=1e-2, ge=1e-6, le=1e3, title="Tolerance Pipes")

    crack_radius: float = Field(default=0.1, ge=0.01, le=100, title="Crack Radius")


class EnvelopeSettings(BaseModel):
    show_intrados: bool = Field(default=True, title="Show Intrados")
    show_middle: bool = Field(default=False, title="Show Middle")
    show_extrados: bool = Field(default=True, title="Show Extrados")


class BlockModelSettings(BaseModel):
    tol_contacts: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Tolerance Contacts")
    amin_contacts: float = Field(default=1e-2, ge=1e-6, le=90, title="Minimum Angle Contacts")

    show_blocks: bool = Field(default=True, title="Show Blocks")
    show_supports: bool = Field(default=True, title="Show Supports")
    show_contacts: bool = Field(default=False, title="Show Contacts")
    show_interactions: bool = Field(default=False, title="Show Interactions")
    show_selfweight: bool = Field(default=False, title="Show Selfweight")
    show_reactions: bool = Field(default=False, title="Show Reactions")

    scale_selfweight: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Selfweight")
    scale_reactions: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Reactions")


class MasonrySettings(Settings):
    autoupdate: bool = Field(default=True, title="Auto Update")
    autosave: bool = Field(default=False, title="Auto Save")

    formdiagram: FormDiagramSettings = FormDiagramSettings()
    envelope: EnvelopeSettings = EnvelopeSettings()
    blockmodel: BlockModelSettings = BlockModelSettings()
