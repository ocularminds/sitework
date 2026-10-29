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
