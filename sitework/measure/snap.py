"""Edge snapping: refine a model-proposed line to the straight image edge it points at.

The model says roughly where an edge is; this module finds the edge in the pixels. Along the
proposal it reads short gradient profiles perpendicular to it, takes the strongest edge in each,
fits a line robustly, and reports how well the image supports that line. No clear edge, no snap.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from sitework.measure.geometry import Line


@dataclass(frozen=True)
class Snap:
    segment: np.ndarray  # (2, 2) px: the proposal's endpoints projected onto the fitted edge
    support: float  # share of profiles whose edge lies on the fitted line
    residual_px: float  # RMS distance of those edge points from the line
    quality: float  # support x (1 - residual / MAX_RESIDUAL_PX), 0..1


class Gradients:
    """Smoothed intensity gradients of one frame (intensity units per pixel)."""

    def __init__(self, image: np.ndarray):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        smooth = cv2.GaussianBlur(gray.astype(np.float32), (5, 5), 1.2)
        self.gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        self.gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        self.height, self.width = gray.shape

    def along(self, points: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """Derivative of intensity along `direction` at each (x, y) point; 0 outside the image."""
        mx = points[:, 0].astype(np.float32).reshape(1, -1)
        my = points[:, 1].astype(np.float32).reshape(1, -1)
        gx = cv2.remap(self.gx, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        gy = cv2.remap(self.gy, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return (gx * direction[0] + gy * direction[1]).ravel()


class EdgeSnapper:
    """`polarity` +1/-1 asks for intensity rising/falling along `inward`; 0 accepts either."""

    MAX_RESIDUAL_PX = 4.0  # starting value: a 1 px fit residual scores 0.75; calibrate with eval
    INLIER_PX = 2.0

    def __init__(self, reach_frac: float = 0.04, samples: int = 40, step_px: float = 0.5,
                 min_contrast: float = 4.0, min_support: float = 0.6):
        self.reach_frac = reach_frac  # search distance either side, as a share of the longer image side
        self.samples = samples
        self.step_px = step_px
        self.min_contrast = min_contrast  # weakest edge accepted, intensity units per pixel
        self.min_support = min_support

    def snap(self, grads: Gradients, segment, polarity: int = 0, inward: np.ndarray | None = None) -> Snap | None:
        p0, p1 = (np.asarray(p, dtype=np.float64) for p in segment)
        length = float(np.linalg.norm(p1 - p0))
        if length < 5.0:
            return None
        d = (p1 - p0) / length
        n = np.array([-d[1], d[0]])
        if inward is not None and float(np.dot(n, inward)) < 0:
            n = -n
        reach = self.reach_frac * max(grads.width, grads.height)
        offsets = np.arange(-reach, reach + self.step_px, self.step_px)
        centres = p0 + np.outer(np.linspace(0.1, 0.9, self.samples) * length, d)
        grid = centres[:, None, :] + offsets[None, :, None] * n
        profile = grads.along(grid.reshape(-1, 2), n).reshape(self.samples, len(offsets))
        score = polarity * profile if polarity else np.abs(profile)
        idx = score.argmax(axis=1)
        rows = np.arange(self.samples)
        found = score[rows, idx] >= self.min_contrast
        offset = offsets[idx] + self._subpixel(score, idx) * self.step_px
        points = (centres + offset[:, None] * n)[found]
        if len(points) < max(3, self.min_support * self.samples):
            return None
        line = self._robust_line(points)
        inliers = points[line.distance(points) <= self.INLIER_PX]
        support = len(inliers) / self.samples
        if support < self.min_support or len(inliers) < 3:
            return None
        line = Line.fit(inliers)
        residual = float(np.sqrt(np.mean(line.distance(inliers) ** 2)))
        ends = np.array([line.point + float(np.dot(p - line.point, line.direction)) * line.direction for p in (p0, p1)])
        quality = support * max(0.0, 1.0 - residual / self.MAX_RESIDUAL_PX)
        return Snap(ends, round(support, 3), round(residual, 3), round(quality, 3))

    @staticmethod
    def _subpixel(score: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Parabolic peak refinement, in steps; 0 at the profile ends."""
        inner = (idx > 0) & (idx < score.shape[1] - 1)
        out = np.zeros(len(idx))
        r = np.arange(len(idx))[inner]
        a, b, c = score[r, idx[inner] - 1], score[r, idx[inner]], score[r, idx[inner] + 1]
        denom = a - 2 * b + c
        out[inner] = np.where(np.abs(denom) > 1e-9, 0.5 * (a - c) / np.where(denom == 0, 1, denom), 0.0)
        return np.clip(out, -0.5, 0.5)

    def _robust_line(self, points: np.ndarray) -> Line:
        line = Line.fit(points)
        for _ in range(3):
            r = line.distance(points)
            keep = r <= max(self.INLIER_PX, 2.5 * float(np.median(r)))
            if keep.sum() < 3:
                break
            line = Line.fit(points[keep])
        return line
