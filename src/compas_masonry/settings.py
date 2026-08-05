from pydantic import BaseModel
from pydantic import Field

from compas_session.settings import Settings


class FormDiagramSettings(BaseModel):
    show_reactions: bool = Field(default=True, title="Show Reactions")
    show_pipes: bool = Field(default=False, title="Show Pipes")
    show_loads: bool = Field(default=True, title="Show Loads")
    show_bounds: bool = Field(default=False, title="Show Bounds")
    show_cracks: bool = Field(default=False, title="Show Cracks")
    show_labels: bool = Field(default=False, title="Show Labels")

    scale_reactions: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Reactions")
    scale_pipes: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Pipes")
    scale_loads: float = Field(default=0.1, ge=1e-6, le=1e3, title="Scale Loads")

    tol_vectors: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Tolerance Vectors")
    tol_pipes: float = Field(default=1e-2, ge=1e-6, le=1e3, title="Tolerance Pipes")

    crack_radius: float = Field(default=0.1, ge=0.01, le=100, title="Crack Radius")


class EnvelopeSettings(BaseModel):
    show_intrados: bool = Field(default=True, title="Show Intrados")
    show_middle: bool = Field(default=False, title="Show Middle")
    show_extrados: bool = Field(default=True, title="Show Extrados")
    show_fill: bool = Field(default=True, title="Show Fill")


class BlockModelSettings(BaseModel):
    tol_contacts: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Tolerance Contacts")
    amin_contacts: float = Field(default=1e-2, ge=1e-6, le=90, title="Minimum Angle Contacts")

    show_blocks: bool = Field(default=True, title="Show Blocks")
    show_supports: bool = Field(default=True, title="Show Supports")
    show_contacts: bool = Field(default=False, title="Show Contacts")
    show_interactions: bool = Field(default=False, title="Show Interactions")
    show_selfweight: bool = Field(default=False, title="Show Selfweight")
    show_reactions: bool = Field(default=False, title="Show Reactions")
    show_normalforces: bool = Field(default=False, title="Show Normal Forces")
    show_frictionforces: bool = Field(default=False, title="Show Friction Forces")
    show_resultants: bool = Field(default=False, title="Show Resultants")
    show_wireframe: bool = Field(default=False, title="Show Wireframe")

    scale_selfweight: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Selfweight")
    scale_reactions: float = Field(default=0.01, ge=1e-6, le=1e3, title="Scale Reactions")

    # Problem load/BC display scales — Rhino length drawn per unit of the
    # underlying quantity (see MasonrySession.draw_problem).
    scale_loads: float = Field(default=1e-3, ge=1e-9, le=1e6, title="Scale Loads (m per N)")
    scale_gravity: float = Field(default=0.1, ge=1e-6, le=1e3, title="Scale Gravity (m per m/s2)")
    scale_displacement: float = Field(default=1.0, ge=1e-6, le=1e6, title="Scale Displacement/Rotation BC")

    # Contact force results. DIMENSIONLESS, unlike the scales above: at 1.0 the
    # largest resultant of a result set is drawn half as long as the biggest
    # block is wide, so forces are visible without per-model tuning whatever
    # the units are. See MasonrySession.draw_result_forces.
    scale_forces: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Result Forces (relative)")

    # How far to fade the model's blocks while results are drawn on top of them.
    # 0 = untouched (colour by layer), 1 = white. Applied as a custom OBJECT
    # colour, so it shows in every display mode — see MasonrySession.fade_model.
    results_model_transparency: float = Field(default=0.8, ge=0.0, le=1.0, title="Fade Blocks When Showing Results")

    contact_tolerance: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Contact Tolerance")
    contact_minimum_area: float = Field(default=1e-2, ge=1e-6, le=90, title="Contact Minimum Area")


class MasonrySettings(Settings):
    autoupdate: bool = Field(default=True, title="Auto Update")
    autosave: bool = Field(default=False, title="Auto Save")

    # How commands ask for their parameters: False = command line options
    # (Rhino.Input.Custom), True = an Eto dialog with the same fields.
    # Read by compas_masonry.inputs.Options.get().
    dialog_input: bool = Field(default=False, title="Use Dialogs For Command Input")

    # Directory holding the solver executables the CRA/RBE backends shell out
    # to. compas_cra builds its pyomo model against `ipopt`, which it looks up
    # on PATH — and Rhino, launched from the Finder, does not inherit a shell
    # PATH, so the conda binary is invisible to it. Prepended by
    # MasonrySession.ensure_solver_path() only when the lookup already fails.
    solver_bin: str = Field(default="/opt/anaconda3/envs/masonry/bin", title="Solver Executables Directory")

    formdiagram: FormDiagramSettings = FormDiagramSettings()
    envelope: EnvelopeSettings = EnvelopeSettings()
    blockmodel: BlockModelSettings = BlockModelSettings()
