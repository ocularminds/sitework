"""ArUco fiducial: real-world scale and a homography from image pixels to the marker plane."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Scale:
    """Maps image pixels onto the plane the marker lies on, in millimetres."""

    marker_id: int
    corners_px: np.ndarray  # (4, 2) in detector order: TL, TR, BR, BL
    homography: np.ndarray  # 3x3, pixels -> mm
    px_per_mm: float
    quality: float  # 0..1

    def to_mm(self, points_px: np.ndarray) -> np.ndarray:
        pts = np.asarray(points_px, dtype=np.float64).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.homography).reshape(-1, 2)


class Fiducial:
    """Finds one ArUco DICT_4X4_50 marker of known size.

    Quality falls when the marker looks skewed (unequal sides) or small in the image,
    because both make the millimetre scale less certain.
    """

    MIN_SIDE_PX = 60.0  # below this, one pixel of corner error is > ~1.5 % of a 40 mm side

    def __init__(self, marker_mm: float = 40.0, marker_id: int | None = None):
        self.marker_mm = marker_mm
        self.marker_id = marker_id
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self._detector = cv2.aruco.ArucoDetector(dictionary, params)

    def detect(self, image: np.ndarray) -> Scale | None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        corners, ids, _ = self._detector.detectMarkers(gray)
        if ids is None:
            return None
        candidates = [(int(i), c.reshape(4, 2).astype(np.float64)) for i, c in zip(ids.ravel(), corners)]
        if self.marker_id is not None:
            candidates = [c for c in candidates if c[0] == self.marker_id]
        if not candidates:
            return None
        marker_id, px = max(candidates, key=lambda c: cv2.contourArea(c[1].astype(np.float32)))
        m = self.marker_mm
        plane = np.array([[0, 0], [m, 0], [m, m], [0, m]], dtype=np.float64)
        homography = cv2.getPerspectiveTransform(px.astype(np.float32), plane.astype(np.float32))
        sides = np.linalg.norm(px - np.roll(px, -1, axis=0), axis=1)
        quality = float(min(sides.min() / sides.max(), 1.0) * min(sides.mean() / self.MIN_SIDE_PX, 1.0))
        return Scale(marker_id, px, homography, float(sides.mean() / m), round(quality, 3))
