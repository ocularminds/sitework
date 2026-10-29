"""Decking measurements: board gaps and out-of-parallel angle from model board corners."""

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
    OVERLAP_MM = 0.5  # adjacent boards may touch; more overlap than this means a misread

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
            if float((far.ends.mean(axis=0) - near.ends.mean(axis=0)) @ normal) < -self.OVERLAP_MM:
                raise ValueError("two of the model's boards overlap (the same board twice?)")
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
        so neither can jump to the neighbouring board's edge across a gap.

        Both readings are tried: a board darker than its surroundings, and a lighter one. The
        reading whose weaker edge is the stronger, better-fitted one wins; grain inside a board
        is straight too, but much fainter than the board's boundary. A different reading nearly
        as good as the winner lowers the quality, because the image then supports both."""
        mids = [np.mean(np.asarray(e, dtype=float), axis=0) for e in edges]
        inward = [mids[1] - mids[0], mids[0] - mids[1]]
        readings = []
        for polarity in (-1, 1):
            snaps = [self.snapper.snap(grads, e, polarity, inward[i]) for i, e in enumerate(edges)]
            if all(snaps):
                readings.append((min(sn.quality * sn.strength for sn in snaps), snaps))
        if not readings:
            raise ValueError(f"no clear image edges for board {index + 1}")
        readings.sort(key=lambda r: r[0], reverse=True)
        score, snaps = readings[0]
        quality = min(sn.quality for sn in snaps)
        if len(readings) > 1 and self._differ(snaps, readings[1][1]):
            margin = 1.0 - readings[1][0] / score if score > 0 else 0.0
            quality *= min(1.0, margin / self.snapper.CLEAR)
        return [sn.segment.tolist() for sn in snaps], round(quality, 3)

    def _differ(self, a: list, b: list) -> bool:
        """Whether two readings put either edge in a different place."""
        return any(float(np.linalg.norm(x.segment.mean(axis=0) - y.segment.mean(axis=0))) > self.snapper.INLIER_PX
                   for x, y in zip(a, b))

    @staticmethod
    def _edge(segment: list, scale: Scale) -> Edge:
        ends = scale.to_mm(np.array(segment))
        return Edge(Line.fit(ends), ends)
