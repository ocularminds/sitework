import cv2
import numpy as np
import pytest

from sitework.measure.deck import DeckMeasurer
from sitework.measure.fiducial import Fiducial
from sitework.measure.snap import EdgeSnapper, Gradients
from sitework.measure.trench import TrenchMeasurer
from sitework.perceive.views import DeckingView, TrenchView
from synth import deck_scene, deck_view, scene_with_marker, trench_scene, trench_view


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


def test_a_rival_edge_as_strong_as_the_chosen_one_lowers_the_quality():
    stripe = step_image()
    y, x = np.mgrid[0:400, 0:600]
    stripe[(y > 215 + (x - 100) * np.tan(np.radians(2.0)))] = 190  # a 15 px dark band: two near-equal edges
    snap = EdgeSnapper().snap(Gradients(stripe), [[100, edge_y(100)], [500, edge_y(500)]])
    assert snap is not None and 0 < snap.clarity < 0.2 and snap.quality < 0.4


def test_the_snapped_segment_runs_from_where_the_edge_starts_to_where_it_stops():
    img = step_image()
    img[:, :150] = img[:, 450:] = 200  # the edge now exists only for 150 <= x < 450
    snap = EdgeSnapper().snap(Gradients(img), [[120, edge_y(120) + 6], [480, edge_y(480) + 6]])
    assert snap.ends_found == (True, True)
    assert snap.segment[0][0] == pytest.approx(150, abs=1.5) and snap.segment[1][0] == pytest.approx(450, abs=1.5)


def test_grain_lines_along_the_boards_do_not_pull_the_edges_off(scale):
    image, truth = deck_scene(2.0, 5.0, grained=True)
    s = DeckMeasurer(EdgeSnapper()).sample(deck_view(2.0, 7.0), scale, 0, image)
    assert s.angle_deg == pytest.approx(2.0, abs=0.15) and s.gap_min_mm == pytest.approx(5.0, abs=0.2)


def test_the_same_board_twice_is_an_error_not_a_wide_gap(scale):
    image, view = deck_scene(2.0, 5.0)
    twice = DeckingView(confidence=0.9, boards=[view.boards[0], view.boards[0]])
    with pytest.raises(ValueError, match="overlap"):
        DeckMeasurer(EdgeSnapper()).sample(twice, scale, 0, image)


def shifted_wall(view: TrenchView, top_px: float, toe_px: float) -> TrenchView:
    """The view's wall with its top and toe slid along the wall by the given pixels (+ = towards the toe)."""
    top, toe = (np.array(p) for p in (view.walls[0].top, view.walls[0].toe))
    d = (toe - top) / np.linalg.norm(toe - top)
    return TrenchView(confidence=view.confidence, walls=[{"top": (top + top_px * d).tolist(),
                                                           "toe": (toe + toe_px * d).tolist()}])


@pytest.mark.parametrize("blur,tol", [(0, 0.5), (4, 1.0)])
def test_trench_depth_comes_from_the_wall_ends_in_the_image_not_the_model(scale, blur, tol):
    image, truth = trench_scene(60.0, 40.0)
    image = cv2.GaussianBlur(image, (0, 0), blur) if blur else image
    for top_px, toe_px in [(25, -30), (-20, 20)]:  # the model's ends short of, then past, the corners
        s = TrenchMeasurer(EdgeSnapper()).sample(shifted_wall(truth, top_px, toe_px), scale, 0, image)
        assert s.slope_deg == pytest.approx(60.0, abs=0.3) and s.depth_mm == pytest.approx(40.0, abs=tol)


def test_a_wall_running_out_of_the_picture_has_no_clear_end_so_it_is_an_error(scale):
    image, _ = trench_scene(60.0, 40.0)
    cropped = np.ascontiguousarray(image[:500])  # the toe (about y = 524) is below the frame
    with pytest.raises(ValueError, match="no clear end"):
        TrenchMeasurer(EdgeSnapper()).sample(trench_view(60.0, 40.0), scale, 0, cropped)
