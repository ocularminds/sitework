import numpy as np
import pytest

from sitework.measure.deck import DeckMeasurer
from sitework.measure.fiducial import Fiducial
from sitework.measure.snap import EdgeSnapper, Gradients
from synth import deck_scene, deck_view, scene_with_marker


def step_image(angle_deg: float = 2.0) -> np.ndarray:
    """Dark below a straight line through (100, 200) at angle_deg, light above it."""
    y, x = np.mgrid[0:400, 0:600].astype(np.float64)
    a = np.radians(angle_deg)
    side = (y - 200) * np.cos(a) - (x - 100) * np.sin(a)
    return np.where(side > 0, 60, 200).astype(np.uint8)


def edge_y(x: float, angle_deg: float = 2.0) -> float:
    return 200 + (x - 100) * np.tan(np.radians(angle_deg))


@pytest.fixture(scope="module")
def grads():
    return Gradients(step_image())


def test_an_offset_proposal_snaps_onto_the_edge(grads):
    proposal = [[100, edge_y(100) - 12], [500, edge_y(500) - 12]]
    snap = EdgeSnapper().snap(grads, proposal)
    assert snap is not None and snap.quality > 0.9
    for (x, y) in snap.segment:
        assert y == pytest.approx(edge_y(x), abs=0.5)


def test_polarity_selects_which_way_the_edge_must_go(grads):
    proposal = [[100, edge_y(100)], [500, edge_y(500)]]
    down = np.array([0.0, 1.0])  # intensity falls from light (above) to dark (below)
    assert EdgeSnapper().snap(grads, proposal, polarity=-1, inward=down) is not None
    assert EdgeSnapper().snap(grads, proposal, polarity=+1, inward=down) is None


def test_no_edge_in_reach_or_a_crossing_edge_gives_no_snap(grads):
    assert EdgeSnapper().snap(Gradients(np.full((400, 600), 128, np.uint8)), [[100, 200], [500, 200]]) is None
    assert EdgeSnapper().snap(grads, [[100, 100], [500, 100]]) is None  # 100 px away, beyond reach
    assert EdgeSnapper().snap(grads, [[300, 60], [300, 340]]) is None  # crosses the edge, not along it


@pytest.fixture(scope="module")
def scale():
    return Fiducial(40.0).detect(scene_with_marker())


def test_a_rough_deck_proposal_measures_the_drawn_boards(scale):
    image, _ = deck_scene(2.0, 5.0)
    rough = deck_view(2.0, 7.0)  # the model put the second board 2 mm too far out
    s = DeckMeasurer(EdgeSnapper()).sample(rough, scale, 0, image)
    assert s.angle_deg == pytest.approx(2.0, abs=0.15) and s.gap_min_mm == pytest.approx(5.0, abs=0.2)
    assert s.point_quality > 0.9 and len(s.segments) == 4


def test_boards_with_no_image_edges_raise_so_the_frame_is_an_error(scale):
    with pytest.raises(ValueError, match="no clear image edges"):
        DeckMeasurer(EdgeSnapper()).sample(deck_view(2.0, 5.0), scale, 0, scene_with_marker())
