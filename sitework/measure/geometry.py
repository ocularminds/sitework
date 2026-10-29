"""Pure geometry on plane coordinates (mm). No models, no I/O."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Line:
    """An infinite line through `point` along unit `direction`."""

    point: np.ndarray
    direction: np.ndarray

    @classmethod
    def fit(cls, points: np.ndarray) -> "Line":
        """Total least squares fit; needs at least two distinct points."""
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if len(pts) < 2:
            raise ValueError("a line needs at least two points")
        centroid = pts.mean(axis=0)
        _, s, vt = np.linalg.svd(pts - centroid)
        if s[0] == 0:
            raise ValueError("points are identical")
        return cls(centroid, vt[0] / np.linalg.norm(vt[0]))

    @property
    def orientation_deg(self) -> float:
        """Direction angle folded into [0, 180)."""
        return float(np.degrees(np.arctan2(self.direction[1], self.direction[0])) % 180.0)

    def distance(self, points: np.ndarray) -> np.ndarray:
        """Perpendicular distance of each point to the line."""
        normal = np.array([-self.direction[1], self.direction[0]])
        return np.abs((np.asarray(points, dtype=np.float64).reshape(-1, 2) - self.point) @ normal)


def angle_between(a: Line, b: Line) -> float:
    """Acute angle between two lines in degrees, 0..90."""
    cos = abs(float(np.dot(a.direction, b.direction)))
    return float(np.degrees(np.arccos(min(cos, 1.0))))


def mean_direction(lines: list[Line]) -> Line:
    """Average of nearly parallel lines (signs aligned), through their mean point."""
    ref = lines[0].direction
    dirs = [ln.direction if np.dot(ln.direction, ref) >= 0 else -ln.direction for ln in lines]
    d = np.mean(dirs, axis=0)
    return Line(np.mean([ln.point for ln in lines], axis=0), d / np.linalg.norm(d))


def gap_range(edge: Line, facing: np.ndarray) -> tuple[float, float]:
    """Smallest and largest distance from the facing edge's endpoints to `edge`.

    For two straight edges the distance is linear along the joint, so its extremes
    sit at the endpoints of the measured span.
    """
    d = edge.distance(facing)
    return float(d.min()), float(d.max())
