"""Edge snapping: refine a model-proposed line to the straight image edge it points at.

The model says roughly where an edge is; this module finds the edge in the pixels. Along the
proposal it reads short gradient profiles perpendicular to it, takes the strongest edge in each,
fits a line robustly, and reports how well the image supports that line. It then walks along the
fitted line to find where the edge starts and stops. No clear edge, no snap.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from sitework.measure.geometry import Line


@dataclass(frozen=True)
class Snap:
    segment: np.ndarray  # (2, 2) px on the fitted edge: where it starts and stops, else the proposal's ends
    support: float  # share of profiles whose edge lies on the fitted line
    residual_px: float  # RMS distance of those edge points from the line
    strength: float  # median contrast of the edge, intensity units per pixel
    clarity: float  # 1 - median (rival / chosen) edge strength across profiles; 0 when a rival is as strong
    ends_found: tuple[bool, bool]  # whether the edge visibly stops near each end of the proposal
    quality: float  # support x (1 - residual / MAX_RESIDUAL_PX) x min(1, clarity / CLEAR), 0..1


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
    CLEAR = 0.5  # a rival edge up to half as strong as the chosen one costs nothing
    SAME_EDGE_PX = 3.0  # peaks closer than this to the chosen one are the same edge, not a rival
    GAP_PX = 3.0  # breaks in an edge shorter than this (noise, a raindrop) do not end it
    END_BAND_PX = 1.0  # half-width of the band read along the fitted line when looking for its ends
    BORDER_PX = 4.0  # an edge that stops this close to the image border ran out of the picture

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
        peak = score[rows, idx]
        found = peak >= self.min_contrast
        offset = offsets[idx] + self._subpixel(score, idx) * self.step_px
        points = (centres + offset[:, None] * n)[found]
        if len(points) < max(3, self.min_support * self.samples):
            return None
        line = self._robust_line(points)
        inlier = line.distance(points) <= self.INLIER_PX
        support = int(inlier.sum()) / self.samples
        if support < self.min_support or inlier.sum() < 3:
            return None
        line = Line.fit(points[inlier])
        residual = float(np.sqrt(np.mean(line.distance(points[inlier]) ** 2)))
        strength = float(np.median(peak[found][inlier]))
        clarity = 1.0 - float(np.median(self._rivals(score, idx)[found][inlier] / peak[found][inlier]))
        direction = line.direction if float(np.dot(line.direction, d)) >= 0 else -line.direction
        normal = np.array([-direction[1], direction[0]])
        normal = normal if float(np.dot(normal, n)) >= 0 else -normal
        s0, s1 = (float(np.dot(p - line.point, direction)) for p in (p0, p1))
        (s0, s1), ends_found = self._extent(grads, line.point, direction, normal, polarity, s0, s1, reach)
        ends = np.array([line.point + s * direction for s in (s0, s1)])
        quality = support * max(0.0, 1.0 - residual / self.MAX_RESIDUAL_PX) * min(1.0, clarity / self.CLEAR)
        return Snap(ends, round(support, 3), round(residual, 3), round(strength, 2), round(clarity, 3),
                    ends_found, round(quality, 3))

    def _rivals(self, score: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Per profile, the strongest other peak: a local maximum away from the chosen edge, so the
        shoulder of a blurred edge is not mistaken for a second one (0 if there is none)."""
        cols = np.arange(score.shape[1])
        same = np.abs(cols[None, :] - idx[:, None]) <= self.SAME_EDGE_PX / self.step_px
        padded = np.pad(score, ((0, 0), (1, 1)), constant_values=-np.inf)
        peak = (score >= padded[:, :-2]) & (score >= padded[:, 2:])
        return np.clip(np.where(peak & ~same, score, -np.inf).max(axis=1), 0.0, None)

    def _extent(self, grads: Gradients, point: np.ndarray, direction: np.ndarray, normal: np.ndarray,
                polarity: int, s0: float, s1: float, reach: float) -> tuple[tuple[float, float], tuple[bool, bool]]:
        """Where along the fitted line the edge starts and stops: the run of positions whose edge
        strength stays above half its typical value, around the proposal's middle. Gradient along
        the line counts against it, so an edge meeting this one at a corner does not extend it.
        An end that runs past the search keeps the proposal's position and is reported as not found."""
        s = np.arange(s0 - reach, s1 + reach + self.step_px, self.step_px)
        across = np.arange(-self.END_BAND_PX, self.END_BAND_PX + 1e-9, self.step_px)
        grid = (point + s[:, None, None] * direction + across[None, :, None] * normal).reshape(-1, 2)
        prof = grads.along(grid, normal).reshape(len(s), len(across))
        lengthwise = np.abs(grads.along(grid, direction)).reshape(len(s), len(across))
        strength = ((polarity * prof if polarity else np.abs(prof)) - lengthwise).max(axis=1)
        middle = (s >= s0 + 0.25 * (s1 - s0)) & (s <= s0 + 0.75 * (s1 - s0))
        level = max(self.min_contrast, 0.5 * float(np.median(strength[middle])))
        on = self._closed(strength >= level, int(round(self.GAP_PX / self.step_px)))
        mid = int(np.argmin(np.abs(s - (s0 + s1) / 2)))
        if not on[mid]:
            return (s0, s1), (False, False)
        start, end = mid, mid
        while start > 0 and on[start - 1]:
            start -= 1
        while end < len(s) - 1 and on[end + 1]:
            end += 1
        lo = self._crossing(s, strength, level, start, start - 1) if start > 0 else None
        hi = self._crossing(s, strength, level, end, end + 1) if end < len(s) - 1 else None
        found = tuple(e is not None and self._inside(grads, point + e * direction) for e in (lo, hi))
        return (lo if found[0] else s0, hi if found[1] else s1), found

    def _inside(self, grads: Gradients, p: np.ndarray) -> bool:
        m = self.BORDER_PX
        return m <= p[0] <= grads.width - 1 - m and m <= p[1] <= grads.height - 1 - m

    @staticmethod
    def _closed(on: np.ndarray, k: int) -> np.ndarray:
        """Morphological closing: fill runs of off shorter than about 2k samples."""
        kernel = np.ones(2 * k + 1)
        grown = np.convolve(on.astype(float), kernel, "same") > 0
        return np.convolve((~grown).astype(float), kernel, "same") == 0

    @staticmethod
    def _crossing(s: np.ndarray, strength: np.ndarray, level: float, inside: int, outside: int) -> float:
        """Where strength falls through `level` between an inside and the next outside sample."""
        a, b = strength[inside], strength[outside]
        t = 0.0 if a == b else float(np.clip((a - level) / (a - b), 0.0, 1.0))
        return float(s[inside] + t * (s[outside] - s[inside]))

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
