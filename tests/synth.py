"""Synthetic bench scenes: a marker and deck boards on a plane seen in perspective."""

import math

import cv2
import numpy as np

from sitework.perceive.views import DeckingView

# A plane (mm) seen in perspective: plane mm -> image px.
H = np.array([[4.0, 0.3, 200.0], [0.1, 3.8, 150.0], [0.0002, 0.0001, 1.0]])


def to_px(points_mm) -> np.ndarray:
    return cv2.perspectiveTransform(np.array(points_mm, float).reshape(-1, 1, 2), H).reshape(-1, 2)


def scene_with_marker(marker_mm: float = 40.0) -> np.ndarray:
    """A white image with a 4x4_50 marker covering [0, marker_mm]^2 on the plane."""
    img = np.full((900, 1400, 3), 255, np.uint8)
    marker = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 3, 400)
    src = np.float32([[0, 0], [400, 0], [400, 400], [0, 400]])
    dst = to_px([[0, 0], [marker_mm, 0], [marker_mm, marker_mm], [0, marker_mm]]).astype(np.float32)
    warp = cv2.getPerspectiveTransform(src, dst)
    color = cv2.warpPerspective(cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR), warp, (1400, 900))
    mask = cv2.warpPerspective(np.full((400, 400), 255, np.uint8), warp, (1400, 900))
    img[mask > 0] = color[mask > 0]
    return img


def rotate(p, deg, origin):
    a = math.radians(deg)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return [origin[0] + x * math.cos(a) - y * math.sin(a), origin[1] + x * math.sin(a) + y * math.cos(a)]


def deck_view(angle_deg: float, gap_mm: float, confidence: float = 0.9) -> DeckingView:
    """Two 30 mm boards, 200 mm long; the second is rotated about its near-left corner."""
    b1 = [[[60, 60], [260, 60]], [[60, 90], [260, 90]]]
    origin = (60, 90 + gap_mm)
    b2 = [[rotate(p, angle_deg, origin) for p in edge]
          for edge in ([[60, 90 + gap_mm], [260, 90 + gap_mm]], [[60, 120 + gap_mm], [260, 120 + gap_mm]])]
    return DeckingView(confidence=confidence, boards=[
        {"edges": [to_px(edge).tolist() for edge in board]} for board in (b2, b1)])  # unordered on purpose


def trench_view(slope_deg: float, depth_mm: float, confidence: float = 0.9):
    """A cross-section on the marker plane: ground at y=60 mm, one wall dropping depth_mm at slope_deg."""
    from sitework.perceive.views import TrenchView
    run = depth_mm / math.tan(math.radians(slope_deg))
    top, toe = [120.0, 60.0], [120.0 + run, 60.0 + depth_mm]
    return TrenchView(confidence=confidence, walls=[{"top": to_px([top])[0].tolist(), "toe": to_px([toe])[0].tolist()}])


def plumbing_view(misalign_deg: float, confidence: float = 0.9):
    """A pipe along x into a fitting rotated by misalign_deg, both on the marker plane."""
    from sitework.perceive.views import PlumbingView
    pipe = [[60.0, 100.0], [140.0, 100.0]]
    fitting = [[140.0, 100.0], rotate([200.0, 100.0], misalign_deg, (140.0, 100.0))]
    return PlumbingView(confidence=confidence, pipe=to_px(pipe).tolist(), fitting=to_px(fitting).tolist())


def joint_audio(kind: str, rate: int = 16000):
    """3 s of faint noise, optionally with a 4 kHz seat click or an 80 Hz thud at 1.5 s."""
    import numpy as np
    from sitework.capture import AudioClip
    rng = np.random.default_rng(0)
    y = rng.normal(0, 0.005, 3 * rate).astype(np.float32)
    if kind in ("click", "thud"):
        freq, ms = (4000, 8) if kind == "click" else (80, 60)
        n = int(rate * ms / 1000)
        t = np.arange(n) / rate
        y[int(1.5 * rate):int(1.5 * rate) + n] += (0.8 * np.sin(2 * np.pi * freq * t) * np.exp(-t * 3000 / ms)).astype(np.float32)
    return AudioClip(y, rate, f"synthetic:{kind}")
