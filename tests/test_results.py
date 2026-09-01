"""Headless tests for `compas_masonry.results` — the derived result quantities.

The important case is a result set with **no contact frames**: CRA and RBE never
write one (`_post_processing_cra` stores the polygon, the points and the
resultants, and nothing else). Requiring a frame made stress and reactions come
back empty *silently*, which looked like "this solver reports no stress" rather
than a bug — so it is pinned here.
"""

import pytest

compas = pytest.importorskip("compas")

from compas.geometry import Polygon  # noqa: E402
from compas_masonry.results import CSV_HEADER  # noqa: E402
from compas_masonry.results import application_point_report  # noqa: E402
from compas_masonry.results import application_points  # noqa: E402
from compas_masonry.results import block_result_rows  # noqa: E402
from compas_masonry.results import contact_normal  # noqa: E402
from compas_masonry.results import contact_openings  # noqa: E402
from compas_masonry.results import contact_point  # noqa: E402
from compas_masonry.results import contact_resultants  # noqa: E402
from compas_masonry.results import face_stresses  # noqa: E402
from compas_masonry.results import summary  # noqa: E402
from compas_masonry.results import support_reactions  # noqa: E402
from compas_masonry.results import tension_contacts  # noqa: E402
from compas_masonry.results import tension_report  # noqa: E402


class FakeResults:
    """A Results-shaped stand-in, built the way CRA/RBE leave one.

    Square 1x1 contact in the z=0 plane between blocks 0 and 1, carrying a
    10 N compressive force. No frame and no gaps, exactly like a CRA result.
    """

    def __init__(self, with_frame=False, force=(0.0, 0.0, -10.0), contact=None):
        self._force = list(force)
        self._with_frame = with_frame
        self._contact = contact
        self.metadata = {}
        self.polygon = Polygon([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])

    def contact_data(self, edge):
        return self._contact

    def edges(self):
        return iter([(0, 1)])

    def resultant_global(self, edge):
        return list(self._force)

    def force_magnitude(self, edge):
        return sum(c * c for c in self._force) ** 0.5

    def force_point(self, edge):
        return None

    def contact_frame(self, edge):
        if not self._with_frame:
            return None
        from compas.geometry import Frame

        return Frame([0.5, 0.5, 0.0], [1, 0, 0], [0, 1, 0])

    def contact_polygon(self, edge):
        return self.polygon

    def contact_point(self, edge):
        return [list(p) for p in self.polygon.points]

    def face_contact(self, edge):
        return True

    def gap(self, edge):
        return None

    def node_attribute(self, node, attr):
        return None

    def transformation(self, node):
        return None


class FakeBlock:
    def __init__(self, node, centroid, is_support=False):
        self.graphnode = node
        self.is_support = is_support
        self._centroid = centroid

    @property
    def modelgeometry(self):
        block = self

        class Geometry:
            def centroid(self):
                return block._centroid

        return Geometry()


class FakeModel:
    def __init__(self, blocks):
        self._blocks = blocks

    def elements(self):
        return iter(self._blocks)


@pytest.fixture
def model():
    # block 0 below the contact plane and fixed, block 1 above it
    return FakeModel([FakeBlock(0, [0.5, 0.5, -0.5], is_support=True), FakeBlock(1, [0.5, 0.5, 0.5])])


def test_contact_normal_falls_back_to_the_polygon():
    """No frame is the CRA/RBE case, and it must still yield a normal."""
    assert contact_normal(FakeResults(with_frame=False), (0, 1)) is not None
    assert contact_normal(FakeResults(with_frame=True), (0, 1)) is not None


def test_resultants_without_a_frame():
    resultants = contact_resultants(FakeResults())
    assert len(resultants) == 1
    point, vector, magnitude, edge = resultants[0]
    assert vector == [0.0, 0.0, -10.0]
    assert magnitude == pytest.approx(10.0)
    assert point == pytest.approx([0.5, 0.5, 0.0])  # the polygon centroid


def test_the_resultant_point_beats_the_polygon_centroid():
    """The eccentricity IS the answer — a centroid throws it away.

    CRA writes neither `force_point` nor a contact frame, so the only record of
    *where* on the joint the force acts is the contact's own `resultantpoint`
    (the normal-force-weighted point). Falling straight through to the polygon
    centroid drew every arch resultant on the joint midpoint, which makes the
    thrust line a function of the geometry instead of the solve.
    """
    contact = FakeContact(resultantpoint=[0.8, 0.5, 0.0])
    point, _, _, _ = contact_resultants(FakeResults(contact=contact))[0]
    assert point == pytest.approx([0.8, 0.5, 0.0])


def test_a_contact_without_a_resultant_point_still_falls_back():
    """Not every stored contact object answers `resultantpoint`.

    All three compas_dem contact classes do (FrictionContact weights by normal
    force, EdgeContact by normal force along the line, VertexContact returns the
    point itself), so this is the guard for what a *future* or foreign contact
    object might store — and for `contact_data` being absent entirely, which is
    what a multi-subcontact 3DEC edge produces.
    """
    point, _, _, _ = contact_resultants(FakeResults(contact=DegenerateContact()))[0]
    assert point == pytest.approx([0.5, 0.5, 0.0])


def test_stress_is_force_over_area_without_a_frame():
    """|F . n| / area — 10 N on a 1x1 contact is 10 Pa."""
    stresses = face_stresses(FakeResults())
    assert len(stresses) == 1
    sigma, _, label = stresses[0]
    assert sigma == pytest.approx(10.0)
    assert label == "0-1"


def test_stress_matches_with_and_without_a_frame():
    """The polygon fallback must not change the answer where a frame exists."""
    with_frame = face_stresses(FakeResults(with_frame=True))[0][0]
    without = face_stresses(FakeResults(with_frame=False))[0][0]
    assert with_frame == pytest.approx(without)


def test_support_reaction_without_a_frame(model):
    reactions = support_reactions(FakeResults(), model)
    assert len(reactions) == 1
    node, reaction, magnitude = reactions[0]
    assert node == 0
    assert magnitude == pytest.approx(10.0)
    # block 0 sits on the -normal side, so the stored force is flipped onto it
    assert reaction[2] == pytest.approx(10.0)


def test_openings_are_empty_without_gaps():
    """CRA/RBE write no gaps; that is 'nothing to report', not an error."""
    assert contact_openings(FakeResults()) == []


def test_summary_reports_absent_quantities_as_none(model):
    values = summary(FakeResults(), model)

    assert values["contacts"] == 1
    assert values["force"] == pytest.approx(10.0)
    assert values["force_at"] == "0-1"
    assert values["stress"] == pytest.approx(10.0)
    assert values["reaction"] == pytest.approx(10.0)

    # no gaps and no transformations -> reported as absent, not as a zero maximum
    assert values["opening_at"] is None
    assert values["displacement_at"] is None


# =============================================================================
# Tension
# =============================================================================


class FakeContact:
    """A FrictionContact-shaped stand-in: only the corner-force data is read.

    `tensiondata` rows are `[x, y, z, nx, ny, nz, 0.5 * force]` with a NEGATIVE
    force, which is how compas_dem builds them.
    """

    def __init__(self, tensions=(), resultantpoint=None):
        self.tensiondata = [[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, -0.5 * t] for t in tensions]
        self.resultantpoint = resultantpoint


class DegenerateContact:
    """LMGC90's EdgeContact/VertexContact: no per-corner forces at all."""


def test_no_contact_data_is_not_read_as_no_tension():
    """A contact the solver stored nothing for is skipped, not passed as sound."""
    assert tension_contacts(FakeResults(contact=None)) == []
    assert tension_contacts(FakeResults(contact=DegenerateContact())) == []


def test_tension_is_reported_per_contact_with_the_halving_undone():
    """tensiondata stores half the force; the report must give back the force."""
    results = FakeResults(contact=FakeContact(tensions=[2.0, 6.0]))
    contacts = tension_contacts(results)

    assert len(contacts) == 1
    label, corners, largest = contacts[0]
    assert label == "0-1"
    assert corners == 2
    assert largest == pytest.approx(6.0)


def test_compression_only_reports_nothing():
    assert tension_contacts(FakeResults(contact=FakeContact(tensions=[]))) == []


def test_penalty_tension_is_expected_and_plain_tension_is_not():
    """Same numbers, opposite meaning — metadata['penalty'] is the discriminator."""
    plain = FakeResults(contact=FakeContact(tensions=[3.0]))
    expected, message = tension_report(plain)
    assert expected is False
    assert "should not produce this" in message

    penalty = FakeResults(contact=FakeContact(tensions=[3.0]))
    penalty.metadata["penalty"] = True
    expected, message = tension_report(penalty)
    assert expected is True
    assert "permits tension" in message


def test_no_tension_reports_nothing_at_all():
    assert tension_report(FakeResults(contact=FakeContact())) is None


def test_threedec_tension_uses_native_normal_forces_not_affine_vertex_forces():
    """Exterior resultant reconstruction must not invent native 3DEC tension."""
    results = FakeResults(contact=FakeContact(tensions=[7.1e9]))
    results.metadata["solver"] = "3DEC"
    results.force_normal = lambda edge: [10.0, 20.0, 0.0]

    assert tension_contacts(results) == []

    results.force_normal = lambda edge: [10.0, -2.5, -7.0]
    assert tension_contacts(results) == [("0-1", 2, 7.0)]


# =============================================================================
# CSV rows
# =============================================================================


def _report(contacts, displacement=None):
    return {
        "node": 4,
        "displacement": displacement,
        "contacts": contacts,
        "force_total": sum(c["magnitude"] for c in contacts),
    }


def test_csv_row_per_contact_repeats_the_displacement():
    report = _report(
        [
            {"with": 5, "label": "4-5", "force": [1.0, 2.0, 3.0], "magnitude": 3.7, "stress": 12.0, "opening": None},
            {"with": 6, "label": "4-6", "force": [0.0, 0.0, -1.0], "magnitude": 1.0, "stress": None, "opening": 0.5},
        ],
        displacement=(0.25, [0.0, 0.0, -0.25], "block 4"),
    )

    rows = block_result_rows(report)

    assert len(rows) == 2
    assert all(len(row) == len(CSV_HEADER) for row in rows)
    assert [row[0] for row in rows] == [4, 4]
    assert [row[1] for row in rows] == [5, 6]
    # the displacement is repeated on every row of the block, so the file pivots
    assert rows[0][8:] == rows[1][8:] == [0.25, 0.0, 0.0, -0.25]


def test_csv_writes_missing_values_as_blanks_not_zeros():
    """A stress of 0 and a stress the solver never produced are different answers."""
    report = _report([{"with": 5, "label": "4-5", "force": [0.0, 0.0, 0.0], "magnitude": 0.0, "stress": None, "opening": None}])

    row = block_result_rows(report)[0]

    assert row[6] == ""  # stress
    assert row[7] == ""  # opening
    assert row[8:] == ["", "", "", ""]  # no displacement either


def test_a_block_with_no_contacts_still_gets_a_row():
    """Dropping it would make a block that WAS reported on vanish from the export."""
    rows = block_result_rows(_report([]))

    assert len(rows) == 1
    assert rows[0][0] == 4
    assert len(rows[0]) == len(CSV_HEADER)


# =============================================================================
# Application points
#
# `dropped` is the branch that matters. After the 2026-08-27 fix every compas_dem
# backend writes a `contact_data` answering `resultantpoint`, so `centroid` is
# nearly unreachable and `dropped` is what actually fires in the field: a 3DEC
# edge split into several subcontacts gets a resultant and a magnitude and
# nothing else, and is then missing from the drawing AND from every report while
# still carrying force. Silence is the failure mode, so it is pinned here.
# =============================================================================


def test_application_point_is_solved_when_the_contact_carries_a_resultantpoint():
    results = FakeResults(contact=FakeContact(resultantpoint=[0.25, 0.5, 0.0]))

    solved, centroid, dropped = application_points(results)

    assert (solved, centroid, dropped) == (["0-1"], [], [])
    assert application_point_report(results) is None


def test_application_point_falls_back_to_the_centroid_without_a_resultantpoint():
    """A polygon is a position on the joint, not where the force acts."""
    results = FakeResults(contact=FakeContact())

    solved, centroid, dropped = application_points(results)

    assert (solved, centroid, dropped) == ([], ["0-1"], [])
    assert "joint centroid" in application_point_report(results)


def test_a_contact_with_no_application_point_at_all_is_reported_as_dropped():
    """The 3DEC multi-subcontact case: force present, nowhere to draw it."""
    results = FakeResults(contact=FakeContact())
    results.contact_polygon = lambda edge: None

    solved, centroid, dropped = application_points(results)

    assert (solved, centroid, dropped) == ([], [], ["0-1"])
    message = application_point_report(results)
    assert "no application point at all" in message
    assert "missing from the drawing" in message


def test_a_contact_carrying_no_force_is_not_counted_at_all():
    """Only force-carrying contacts are classified; the rest are not findings."""
    results = FakeResults(contact=FakeContact())
    results.contact_polygon = lambda edge: None
    results.resultant_global = lambda edge: None

    assert application_points(results) == ([], [], [])
    assert application_point_report(results) is None


# =============================================================================
# Display units
#
# Stored mechanics stay in newtons; only what a human reads is converted. The
# conversion lives in one place because the Rhino reaction tag used to divide by
# 1000 on its own while every report printed raw newtons — so a label and the
# table row for the same contact disagreed by 10^3, with nothing on screen
# saying which was which.
# =============================================================================


def test_force_and_stress_conversions_pass_none_through():
    """A quantity the solver never produced is not zero."""
    from compas_masonry.results import to_force_unit, to_stress_unit

    assert to_force_unit(45530.3331) == pytest.approx(45.5303331)
    assert to_stress_unit(1.0e6) == pytest.approx(1000.0)
    assert to_force_unit(None) is None
    assert to_stress_unit(None) is None


def test_the_csv_header_names_its_units():
    """A bare "F_magnitude" is what let the tags say kN while the rows said N."""
    from compas_masonry.results import CSV_HEADER, FORCE_UNIT, STRESS_UNIT

    assert f"F_magnitude_{FORCE_UNIT}" in CSV_HEADER
    assert f"Fx_{FORCE_UNIT}" in CSV_HEADER
    assert f"stress_{STRESS_UNIT}" in CSV_HEADER
    # displacements are lengths, not forces, and are left in model units
    assert "u_magnitude" in CSV_HEADER


def test_csv_rows_are_written_in_display_units():
    report = _report([{"with": 5, "label": "4-5", "force": [1000.0, 2000.0, 3000.0], "magnitude": 45530.3331, "stress": 1.0e6, "opening": None}])

    row = block_result_rows(report)[0]

    assert row[2] == pytest.approx(45.5303331)  # |F| kN
    assert row[3:6] == pytest.approx([1.0, 2.0, 3.0])  # Fx Fy Fz kN
    assert row[6] == pytest.approx(1000.0)  # stress kPa


def test_a_missing_stress_stays_an_empty_cell_rather_than_zero():
    report = _report([{"with": 5, "label": "4-5", "force": [0.0, 0.0, -1.0], "magnitude": 1.0, "stress": None, "opening": None}])

    assert block_result_rows(report)[0][6] == ""


# =============================================================================
# Application point — one resolution order
#
# Two orders is how a reaction ends up drawn somewhere the resultant it sums is
# not. `contact_point()` answers "a representative point ON the contact" and puts
# the frame origin first; for LMGC90 the stored frame is `contact_frames[0]`, the
# FIRST subcontact, which sits at a CORNER of the interface. Measured on a real
# LMGC90 solve: the frame origin was [3.1534, 0.0, 1.5186], exactly polygon
# corner [3.153, 0.0, 1.519], while the force acts at [2.8374, 0.2471, 1.3664].
# =============================================================================


def test_application_point_prefers_the_force_weighted_point_over_the_frame():
    """The LMGC90 case: a frame origin sitting on a corner must not win."""
    from compas_masonry.results import application_point

    results = FakeResults(with_frame=True, contact=FakeContact(resultantpoint=[0.25, 0.4, 0.0]))

    assert application_point(results, (0, 1)) == pytest.approx([0.25, 0.4, 0.0])
    # the frame origin is a different point, and is NOT what was chosen
    assert contact_point(results, (0, 1)) == pytest.approx([0.5, 0.5, 0.0])


def test_application_point_falls_back_to_the_frame_then_the_centroid():
    from compas_masonry.results import application_point

    framed = FakeResults(with_frame=True, contact=FakeContact())
    assert application_point(framed, (0, 1)) == pytest.approx([0.5, 0.5, 0.0])

    bare = FakeResults(contact=FakeContact())
    assert application_point(bare, (0, 1)) == pytest.approx(list(bare.polygon.centroid))


def test_reactions_and_resultants_agree_on_where_a_force_acts(model):
    """They are the same force; drawing them at different points is the bug."""
    from compas_masonry.results import application_point, support_reaction_points

    results = FakeResults(with_frame=True, contact=FakeContact(resultantpoint=[0.25, 0.4, 0.0]))

    assert support_reaction_points(results, model)[0] == pytest.approx(application_point(results, (0, 1)))
