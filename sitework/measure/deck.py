"""Decking measurements: board gaps and out-of-parallel angle from model edge points."""

from dataclasses import dataclass

import numpy as np

from sitework.measure.base import Measurer
from sitework.measure.fiducial import Scale
from sitework.measure.snap import Gradients
from sitework.measure.geometry import Line, angle_between, gap_range, mean_direction
from sitework.perceive.views import DeckingView


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
    point_quality: float
    scale_quality: float
    segments: tuple = ()


class DeckMeasurer(Measurer):
    """Turns board edges into gap and angle on the marker plane."""

    TOLERANCE = {"angle_deg": 0.5, "gap_mm": 0.5}

    def sample(self, view: DeckingView, scale: Scale, frame_index: int, image: np.ndarray | None = None) -> DeckSample:
        grads = self.snapping(image)
        pixel_boards, quality = [b.edges for b in view.boards], view.confidence
        if grads is not None:
            snapped = [self._snap_board(grads, edges, i) for i, edges in enumerate(pixel_boards)]
            pixel_boards, quality = [b for b, _ in snapped], min(q for _, q in snapped)
        boards = [[self._edge(seg, scale) for seg in edges] for edges in pixel_boards]
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
        return DeckSample(frame_index, max(angles), min(gaps), max(gaps), quality, scale.quality,
                          tuple(seg for edges in pixel_boards for seg in edges))

    def series(self, samples: list[DeckSample]) -> dict[tuple[str, str], list[float]]:
        return {
            ("angle_deg", "largest angle between adjacent boards"): [s.angle_deg for s in samples],
            ("gap_mm", "narrowest point of any joint"): [s.gap_min_mm for s in samples],
            ("gap_mm", "widest point of any joint"): [s.gap_max_mm for s in samples],
        }

    def _snap_board(self, grads: Gradients, edges: list, index: int) -> tuple[list, float]:
        """Snap both long edges of one board with the same contrast towards the board's inside,
        so neither can jump to the neighbouring board's edge across a gap."""
        mids = [np.mean(np.asarray(e, dtype=float), axis=0) for e in edges]
        inward = [mids[1] - mids[0], mids[0] - mids[1]]
        best = None
        for polarity in (-1, 1):
            snaps = [self.snapper.snap(grads, e, polarity, inward[i]) for i, e in enumerate(edges)]
            if all(snaps):
                total = sum(sn.quality for sn in snaps)
                if best is None or total > best[0]:
                    best = (total, [sn.segment.tolist() for sn in snaps], min(sn.quality for sn in snaps))
        if best is None:
            raise ValueError(f"no clear image edges for board {index + 1}")
        return best[1], best[2]

    @staticmethod
    def _edge(segment: list, scale: Scale) -> Edge:
        ends = scale.to_mm(np.array(segment))
        return Edge(Line.fit(ends), ends)
