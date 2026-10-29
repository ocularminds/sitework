"""Shared measurement contract: per-frame samples combined into confidence-scored measurements."""

from abc import ABC, abstractmethod
from typing import Protocol

import numpy as np

from sitework.measure.fiducial import Scale
from sitework.perceive.views import View
from sitework.schema import Measurement


class Sample(Protocol):
    frame_index: int
    model_confidence: float
    scale_quality: float


class Measurer(ABC):
    """Measures one frame (`sample`) and combines frames (`combine`).

    Confidence = median model confidence x median fiducial quality x frame agreement, where
    agreement is 1 / (1 + spread / tolerance) for each measured quantity.
    """

    TOLERANCE: dict[str, float]

    @abstractmethod
    def sample(self, view: View, scale: Scale, frame_index: int) -> Sample: ...

    @abstractmethod
    def series(self, samples: list[Sample]) -> dict[tuple[str, str], list[float]]:
        """(kind, what) -> one value per sampled frame."""

    def combine(self, samples: list[Sample], method: str) -> list[Measurement]:
        if not samples:
            return []
        base = float(np.median([s.model_confidence for s in samples])) * float(
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
