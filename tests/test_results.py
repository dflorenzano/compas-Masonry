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
from compas_masonry.results import contact_normal  # noqa: E402
from compas_masonry.results import contact_openings  # noqa: E402
from compas_masonry.results import contact_resultants  # noqa: E402
from compas_masonry.results import face_stresses  # noqa: E402
from compas_masonry.results import summary  # noqa: E402
from compas_masonry.results import support_reactions  # noqa: E402


class FakeResults:
    """A Results-shaped stand-in, built the way CRA/RBE leave one.

    Square 1x1 contact in the z=0 plane between blocks 0 and 1, carrying a
    10 N compressive force. No frame and no gaps, exactly like a CRA result.
    """

    def __init__(self, with_frame=False, force=(0.0, 0.0, -10.0)):
        self._force = list(force)
        self._with_frame = with_frame
        self.metadata = {}
        self.polygon = Polygon([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])

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
