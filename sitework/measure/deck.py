"""Decking measurements: board gaps and out-of-parallel angle from model edge points."""

from dataclasses import dataclass

import numpy as np

from sitework.measure.fiducial import Scale
from sitework.measure.geometry import Line, angle_between, gap_range, mean_direction
from sitework.perceive.views import DeckingView
from sitework.schema import Measurement


@dataclass(frozen=True)
class Edge:
    """One board edge on the marker plane: its fitted line and its two endpoints (mm)."""

    line: Line
    ends: np.ndarray


@dataclass(frozen=True)
class DeckSample:
    """Measurements from one frame."""

    frame_index: int
    angle_deg: float  # largest angle between adjacent boards
    gap_min_mm: float
    gap_max_mm: float
    model_confidence: float
    scale_quality: float


class DeckMeasurer:
    """Turns board edges into gap and angle on the marker plane, then combines frames.

    Confidence = model confidence x fiducial quality x frame agreement, where agreement
    is 1 / (1 + spread / tolerance) over the sampled frames.
    """

    TOLERANCE = {"angle_deg": 0.5, "gap_mm": 0.5}

    def sample(self, view: DeckingView, scale: Scale, frame_index: int) -> DeckSample:
        boards = [[self._edge(seg, scale) for seg in b.edges] for b in view.boards]
        axis = mean_direction([e.line for board in boards for e in board])
        normal = np.array([-axis.direction[1], axis.direction[0]])
        boards.sort(key=lambda board: float(np.mean([e.ends.mean(axis=0) for e in board], axis=0) @ normal))
        angles, gaps = [], []
        for left, right in zip(boards, boards[1:]):
            angles.append(angle_between(mean_direction([e.line for e in left]),
                                        mean_direction([e.line for e in right])))
            near = max(left, key=lambda e: float(e.ends.mean(axis=0) @ normal))
            far = min(right, key=lambda e: float(e.ends.mean(axis=0) @ normal))
            gaps.extend(gap_range(near.line, far.ends))
        return DeckSample(frame_index, max(angles), min(gaps), max(gaps), view.confidence, scale.quality)

    def combine(self, samples: list[DeckSample], method: str) -> list[Measurement]:
        if not samples:
            return []
        base = float(np.median([s.model_confidence for s in samples])) * float(
            np.median([s.scale_quality for s in samples]))
        values = {
            ("angle_deg", "largest angle between adjacent boards"): [s.angle_deg for s in samples],
            ("gap_mm", "narrowest point of any joint"): [s.gap_min_mm for s in samples],
            ("gap_mm", "widest point of any joint"): [s.gap_max_mm for s in samples],
        }
        out = []
        for (kind, what), vals in values.items():
            spread = float(np.std(vals))
            agreement = 1.0 / (1.0 + spread / self.TOLERANCE[kind])
            out.append(Measurement(
                kind=kind, value=round(float(np.median(vals)), 2),
                confidence=round(base * agreement, 3),
                method=f"{method}; {what}; median of {len(vals)} frames, spread {spread:.2f}",
            ))
        return out

    @staticmethod
    def _edge(segment: list, scale: Scale) -> Edge:
        ends = scale.to_mm(np.array(segment))
        return Edge(Line.fit(ends), ends)
