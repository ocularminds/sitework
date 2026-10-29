"""Shared measurement contract: per-frame samples combined into confidence-scored measurements."""

from abc import ABC, abstractmethod
from typing import Protocol

import numpy as np

from sitework.measure.fiducial import Scale
from sitework.measure.snap import EdgeSnapper, Gradients
from sitework.perceive.views import View
from sitework.schema import Measurement


class Sample(Protocol):
    frame_index: int
    point_quality: float  # edge-snap fit quality, or the model's own confidence when not snapping
    scale_quality: float
    segments: tuple  # pixel segments actually measured, for the overlay


class Measurer(ABC):
    """Measures one frame (`sample`) and combines frames (`combine`).

    With a snapper, every model-proposed line is replaced by the image edge it points at and the
    point quality is the snap's fit quality; a line with no clear edge raises ValueError.
    Confidence = median point quality x median fiducial quality x frame agreement, where
    agreement is 1 / (1 + spread / tolerance) for each measured quantity.
    """

    TOLERANCE: dict[str, float]

    def __init__(self, snapper: EdgeSnapper | None = None):
        self.snapper = snapper

    @abstractmethod
    def sample(self, view: View, scale: Scale, frame_index: int, image: np.ndarray | None = None) -> Sample: ...

    @abstractmethod
    def series(self, samples: list[Sample]) -> dict[tuple[str, str], list[float]]:
        """(kind, what) -> one value per sampled frame."""

    def snapping(self, image: np.ndarray | None) -> Gradients | None:
        return Gradients(image) if self.snapper is not None and image is not None else None

    def snap_lines(self, grads: Gradients | None, segments: list, what: str,
                   polarity: int = 0, need_ends: bool = False) -> tuple[list, float | None]:
        """Each segment snapped on its own; (segments, worst quality). A fixed polarity makes a centre
        line inside a solid body snap to the same-side border along its length. With `need_ends`,
        a measurement that depends on where a line stops requires both ends to show in the image."""
        if grads is None:
            return segments, None
        out, qualities = [], []
        for i, seg in enumerate(segments):
            snap = self.snapper.snap(grads, seg, polarity)
            if snap is None:
                raise ValueError(f"no clear image edge near the model's {what} line {i + 1}")
            if need_ends and not all(snap.ends_found):
                raise ValueError(f"the image edge under the model's {what} line {i + 1} has no clear end")
            out.append(snap.segment.tolist())
            qualities.append(snap.quality)
        return out, min(qualities)

    def combine(self, samples: list[Sample], method: str) -> list[Measurement]:
        if not samples:
            return []
        base = float(np.median([s.point_quality for s in samples])) * float(
            np.median([s.scale_quality for s in samples]))
        out = []
        for (kind, what), vals in self.series(samples).items():
            spread = float(np.std(vals))
            agreement = 1.0 / (1.0 + spread / self.TOLERANCE[kind])
            out.append(Measurement(
                kind=kind, value=round(float(np.median(vals)), 2), confidence=round(base * agreement, 3),
                method=f"{method}; {what}; median of {len(vals)} frames, spread {spread:.2f}",
            ))
        return out
