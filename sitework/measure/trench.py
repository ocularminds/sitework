"""Trench measurements: wall slope from horizontal and depth, on the marker's vertical plane.

The marker stands upright in the cross-section plane with its bottom edge level, so the
homography's x axis is horizontal and its y axis is vertical (pointing down, like the image).
"""

import math
from dataclasses import dataclass

import numpy as np

from sitework.measure.base import Measurer
from sitework.measure.fiducial import Scale
from sitework.perceive.views import TrenchView


@dataclass(frozen=True)
class TrenchSample:
    frame_index: int
    slope_deg: float  # steepest wall, degrees from horizontal (90 = vertical)
    depth_mm: float  # deepest wall, vertical drop from top to toe
    point_quality: float
    scale_quality: float
    segments: tuple = ()


class TrenchMeasurer(Measurer):
    """Steep walls are the sensitive case: with little horizontal run, 0.2 mm of corner error is ~0.4°."""

    TOLERANCE = {"slope_deg": 1.0, "depth_mm": 2.0}
    MIN_DROP_MM = 0.5

    def sample(self, view: TrenchView, scale: Scale, frame_index: int, image: np.ndarray | None = None) -> TrenchSample:
        walls, quality = self.snap_lines(self.snapping(image), view.segments(), "wall")
        quality = view.confidence if quality is None else quality
        slopes, depths = [], []
        for top, toe in walls:
            (tx, ty), (bx, by) = scale.to_mm([top, toe])
            dx, dy = abs(bx - tx), abs(by - ty)
            if dy < self.MIN_DROP_MM:
                raise ValueError("a wall's top and toe are at the same height")
            slopes.append(math.degrees(math.atan2(dy, dx)))
            depths.append(dy)
        return TrenchSample(frame_index, max(slopes), max(depths), quality, scale.quality, tuple(walls))

    def series(self, samples: list[TrenchSample]) -> dict[tuple[str, str], list[float]]:
        return {
            ("slope_deg", "steepest wall, degrees from horizontal"): [s.slope_deg for s in samples],
            ("depth_mm", "deepest wall, top to toe"): [s.depth_mm for s in samples],
        }
