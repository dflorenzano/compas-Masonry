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
from compas_masonry.results import block_result_rows  # noqa: E402
from compas_masonry.results import contact_normal  # noqa: E402
from compas_masonry.results import contact_openings  # noqa: E402
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

    def __init__(self, tensions=()):
        self.tensiondata = [[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, -0.5 * t] for t in tensions]


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
