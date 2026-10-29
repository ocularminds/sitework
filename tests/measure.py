import math

import numpy as np
import pytest

from sitework.measure.deck import DeckMeasurer, DeckSample
from sitework.measure.fiducial import Fiducial
from sitework.measure.geometry import Line, angle_between, gap_range
from synth import deck_view, scene_with_marker, to_px

@pytest.fixture(scope="module")
def scale():
    found = Fiducial(40.0).detect(scene_with_marker())
    assert found is not None
    return found


def test_fiducial_recovers_millimetres_through_perspective(scale):
    near = [[10, 10], [60, 10], [60, 60]]
    assert np.allclose(scale.to_mm(to_px(near)), near, atol=0.3)
    # One 40 mm marker extrapolates: error grows with distance (about 1.4 % at 250 mm here).
    far = np.array([[250, 10], [250, 130]])
    assert np.all(np.abs(scale.to_mm(to_px(far)) - far) <= 0.02 * np.linalg.norm(far, axis=1)[:, None])
    assert 0 < scale.quality <= 1


def test_missing_marker_returns_none():
    assert Fiducial().detect(np.full((480, 640, 3), 255, np.uint8)) is None


@pytest.mark.parametrize("angle,gap", [(0.0, 5.0), (3.0, 5.0), (8.0, 3.0)])
def test_deck_angle_and_gap_match_the_constructed_scene(scale, angle, gap):
    s = DeckMeasurer().sample(deck_view(angle, gap), scale, frame_index=0)
    assert s.angle_deg == pytest.approx(angle, abs=0.1)
    assert s.gap_min_mm == pytest.approx(gap, abs=0.3)
    assert s.gap_max_mm == pytest.approx(gap + 200 * math.sin(math.radians(angle)), abs=0.4)


def test_line_geometry_basics():
    a = Line.fit(np.array([[0, 0], [10, 0]]))
    b = Line.fit(np.array([[0, 5], [10, 6]]))
    assert angle_between(a, b) == pytest.approx(math.degrees(math.atan(0.1)))
    assert gap_range(a, np.array([[0, 5], [10, 6]])) == pytest.approx((5.0, 6.0))
    with pytest.raises(ValueError):
        Line.fit(np.array([[1, 1], [1, 1]]))


def test_combine_takes_medians_and_lowers_confidence_when_frames_disagree():
    steady = [DeckSample(i, 3.0, 5.0, 15.0, 0.9, 1.0) for i in range(3)]
    shaky = [DeckSample(0, 1.0, 5.0, 15.0, 0.9, 1.0), DeckSample(1, 3.0, 5.0, 15.0, 0.9, 1.0),
             DeckSample(2, 6.0, 5.0, 15.0, 0.9, 1.0)]
    m = DeckMeasurer()
    steady_angle = m.combine(steady, "test")[0]
    shaky_angle = m.combine(shaky, "test")[0]
    assert steady_angle.kind == "angle_deg" and steady_angle.value == 3.0
    assert steady_angle.confidence == pytest.approx(0.9)
    assert shaky_angle.value == 3.0 and shaky_angle.confidence < 0.3
    assert [x.kind for x in m.combine(steady, "test")] == ["angle_deg", "gap_mm", "gap_mm"]
