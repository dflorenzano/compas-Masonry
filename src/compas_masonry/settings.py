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
    # What `draw_model` puts in the document. Contacts and interactions default
    # off because they are only meaningful after Model_contacts has run, and on a
    # large model they bury the blocks.
    show_blocks: bool = Field(default=True, title="Show Blocks")
    show_supports: bool = Field(default=True, title="Show Supports")
    show_contacts: bool = Field(default=False, title="Show Contacts")
    show_interactions: bool = Field(default=False, title="Show Interactions")

    # What `draw_result_forces` puts in the document, read when Results_show
    # runs. Resultants and reactions are on because they are what the command
    # drew before these flags existed; the decompositions and the self-weight are
    # additions and start off.
    #
    # A resultant, its normal part and its friction part are three views of ONE
    # contact force — `resultant_local` in the contact frame, where z is the
    # normal — so turning all three on draws the same force three times.
    show_resultants: bool = Field(default=True, title="Show Contact Resultants")
    show_reactions: bool = Field(default=True, title="Show Reactions")
    show_normalforces: bool = Field(default=False, title="Show Normal Forces")
    show_frictionforces: bool = Field(default=False, title="Show Friction Forces")
    show_selfweight: bool = Field(default=False, title="Show Selfweight")

    # The per-corner forces the solver actually solved for, before they are summed
    # into the resultant: one along the contact normal at every vertex of the
    # contact polygon, compression and tension drawn in different colours. Off by
    # default because a quad contact draws four extra lines.
    #
    # This is also how a CRA penalty solve is read: the plain formulation forbids
    # tension, the penalty one permits it, and the only way to see WHERE it went is
    # per corner — a resultant that is net compressive hides tensile corners.
    show_cornerforces: bool = Field(default=False, title="Show Corner Forces")

    # Rhino VIEWPORT display mode to switch to while picking sub-objects, and
    # back out of afterwards.
    #
    # There was a `show_wireframe` flag here until 2026-08-20 that drew each
    # block as one line per edge instead of as a mesh. A wireframe LOOK is a
    # viewport display mode's job; doing it by swapping the geometry gave the
    # same picture while emptying the document of the faces and vertices that
    # sub-object picking and the per-block guid tagging both need. Appearance is
    # a display mode here and everywhere, and blocks are always meshes.
    #
    # Vertices default to Wireframe because a shaded surface hides the ones
    # facing away; faces default to Shaded because a wireframe gives them no
    # surface to click. Any name from `rs.ViewDisplayModes()` is valid —
    # Wireframe, Shaded, Rendered, Ghosted, X-Ray, Technical, ... — including a
    # custom mode. Empty leaves the viewport untouched.
    pickmode_face: str = Field(default="Shaded", title="Display Mode While Picking Faces")
    pickmode_vertex: str = Field(default="Wireframe", title="Display Mode While Picking Vertices")

    # Display mode Results_show switches the viewport to, so the force and
    # displacement geometry reads against the blocks instead of disappearing
    # into them. This one is NOT restored afterwards — the point is to leave you
    # looking at the result — so it is a plain set, not the `display_mode`
    # context manager the pickmodes above use. Empty leaves the viewport alone.
    results_display_mode: str = Field(default="Wireframe", title="Display Mode When Showing Results")

    # Relative, on top of `scale_forces` below: at 1.0 a self-weight arrow and a
    # contact resultant of equal length mean equal newtons.
    #
    # `scale_reactions` sat here and was deleted on 2026-08-20. Reaction arrows
    # are contact resultants like any other and are drawn at `scale_forces`; a
    # second scale for them alone would only desynchronise the one picture they
    # are meant to be compared in.
    scale_selfweight: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Selfweight (relative)")

    # Problem boundary-condition display scales. Load arrows use
    # `scale_forces`, so applied loads and result forces share the same
    # geometry-relative convention. Displacements have different physical
    # units and therefore use an independent relative multiplier.
    scale_gravity: float = Field(default=0.1, ge=1e-6, le=1e3, title="Scale Gravity (m per m/s2)")
    scale_displacement_arrows: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Displacement Arrows (relative)")
    scale_displacement: float = Field(default=1.0, ge=1e-6, le=1e6, title="Scale Result Displacements")

    # Contact force results. DIMENSIONLESS, unlike the scales above: at 1.0 the
    # largest resultant of a result set is drawn half as long as the biggest
    # block is wide, so forces are visible without per-model tuning whatever
    # the units are. See MasonrySession.draw_result_forces.
    scale_forces: float = Field(default=1.0, ge=1e-6, le=1e3, title="Scale Result Forces (relative)")

    # `tol_contacts` / `amin_contacts` were merged into these on 2026-08-20.
    # They were an identical second pair, two rows away in the same dialog and
    # read by nothing — so "Tolerance Contacts" silently did nothing while
    # "Contact Tolerance" was what Model_contacts actually used.
    contact_tolerance: float = Field(default=1e-3, ge=1e-6, le=1e3, title="Contact Tolerance")
    contact_minimum_area: float = Field(default=1e-2, ge=1e-6, le=90, title="Contact Minimum Area")


class MasonrySettings(Settings):
    autoupdate: bool = Field(default=True, title="Auto Update")
    autosave: bool = Field(default=False, title="Auto Save")

    # How commands ask for their parameters: False = command line options
    # (Rhino.Input.Custom), True = an Eto dialog with the same fields.
    # Read by compas_masonry.inputs.Options.get().
    dialog_input: bool = Field(default=False, title="Use Dialogs For Command Input")

    # `solver_bin` lived here and was removed on 2026-08-31. It pointed at a
    # directory to prepend to PATH so compas_cra's pyomo model could find the
    # `ipopt` executable; its default was a developer's own conda prefix, which
    # shipped to every user as a path that exists on exactly one machine.
    # compas_cra 0.8.0 runs IPOPT in-process (`compas_cra._native`) and consults
    # no PATH at all, so the setting had nothing left to configure.

    formdiagram: FormDiagramSettings = FormDiagramSettings()
    envelope: EnvelopeSettings = EnvelopeSettings()
    blockmodel: BlockModelSettings = BlockModelSettings()
