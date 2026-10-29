"""Snapping on degraded frames: each measurement is right, refused, or below the confidence floor.

Never confidently wrong is the property that keeps a bad frame from becoming a false ALLOW.
The proposals are the true lines jittered by up to 30 px, about the error seen from the model.
"""

import cv2
import numpy as np
import pytest

from sitework.measure.align import AlignmentMeasurer
from sitework.measure.deck import DeckMeasurer
from sitework.measure.fiducial import Fiducial
from sitework.measure.snap import EdgeSnapper
from sitework.measure.trench import TrenchMeasurer
from synth import deck_scene, plumbing_scene, render, trench_scene

FLOOR = 0.70  # the lowest confidence floor in policies/sitework.json (clean)
JITTER_PX = 30
TRIALS = 4

SCENES = {
    "decking": (lambda: deck_scene(3.0, 5.0, grained=True), DeckMeasurer,
                lambda s: {"angle_deg": s.angle_deg, "gap_min": s.gap_min_mm, "gap_max": s.gap_max_mm}),
    "trench": (lambda: trench_scene(60.0, 40.0), TrenchMeasurer,
               lambda s: {"slope_deg": s.slope_deg, "depth_mm": s.depth_mm}),
    "plumbing": (lambda: plumbing_scene(3.0), AlignmentMeasurer, lambda s: {"angle_deg": s.angle_deg}),
}
TOLERANCE = {"angle_deg": 0.5, "gap_min": 0.5, "gap_max": 0.5, "slope_deg": 1.0, "depth_mm": 2.0}


def degrade(img: np.ndarray, kind: str, rng: np.random.Generator) -> np.ndarray:
    f = img.astype(np.float32)
    h, w = f.shape[:2]
    if kind == "noise":
        f += rng.normal(0, 20, f.shape)
    elif kind == "blur":
        f = cv2.GaussianBlur(f, (0, 0), 4)
    elif kind == "low contrast":
        f = 128 + (f - 128) * 0.35 + rng.normal(0, 4, f.shape)
    elif kind == "shadow":
        f *= np.linspace(0.35, 1.0, w, dtype=np.float32)[None, :, None]
    elif kind == "texture":
        t = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.5)
        f += (t / t.std() * 18)[..., None]
    elif kind == "rain":
        for _ in range(250):
            x, y, length = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(15, 50)
            cv2.line(f, (int(x), int(y)), (int(x + 0.25 * length), int(y + length)), (235, 235, 235), 1, cv2.LINE_AA)
        f = cv2.GaussianBlur(f, (0, 0), 0.8) * 0.85
    elif kind == "glare":
        yy, xx = np.mgrid[0:h, 0:w]
        f += (200 * np.exp(-((xx - 800) ** 2 + (yy - 500) ** 2) / (2 * 160 ** 2)))[..., None]
    return np.clip(f, 0, 255).astype(np.uint8)


def jittered(view, rng: np.random.Generator):
    """The same view with every [x, y] point moved by up to JITTER_PX in x and y."""
    def walk(node):
        if isinstance(node, list) and len(node) == 2 and all(isinstance(v, (int, float)) for v in node):
            return [v + rng.uniform(-JITTER_PX, JITTER_PX) for v in node]
        if isinstance(node, list):
            return [walk(n) for n in node]
        return {k: walk(v) for k, v in node.items()} if isinstance(node, dict) else node
    data = view.model_dump()
    return type(view).model_validate({k: (v if k == "confidence" else walk(v)) for k, v in data.items()})


@pytest.fixture(scope="module")
def clean_scale():
    return Fiducial(40.0).detect(render())


@pytest.mark.parametrize("condition", ["clean", "noise", "blur", "low contrast", "shadow", "texture", "rain", "glare"])
@pytest.mark.parametrize("scene", list(SCENES))
def test_a_degraded_frame_is_measured_right_or_not_trusted(scene, condition, clean_scale):
    make, measurer, values = SCENES[scene]
    rng = np.random.default_rng(7)
    image, truth = make()
    image = degrade(image, condition, rng)
    scale = Fiducial(40.0).detect(image)
    expected = values(measurer().sample(truth, clean_scale, 0))
    for _ in range(TRIALS):
        if scale is None:
            return  # no marker: the frame is an error and escalates
        try:
            s = measurer(EdgeSnapper()).sample(jittered(truth, rng), scale, 0, image)
        except ValueError:
            continue  # refused: the frame is an error and escalates
        wrong = {k: round(v - expected[k], 2) for k, v in values(s).items() if abs(v - expected[k]) > TOLERANCE[k]}
        assert not wrong or s.point_quality * s.scale_quality < FLOOR, f"confidently wrong: {wrong}"
