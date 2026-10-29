"""Plumbing alignment: the angle between the pipe's and the fitting's centre lines on the marker plane."""

from dataclasses import dataclass

import numpy as np

from sitework.measure.base import Measurer
from sitework.measure.fiducial import Scale
from sitework.measure.geometry import Line, angle_between
from sitework.perceive.views import PlumbingView


@dataclass(frozen=True)
class AlignSample:
    frame_index: int
    angle_deg: float
    model_confidence: float
    scale_quality: float


class AlignmentMeasurer(Measurer):
    TOLERANCE = {"angle_deg": 0.5}

    def sample(self, view: PlumbingView, scale: Scale, frame_index: int) -> AlignSample:
        pipe = Line.fit(scale.to_mm(np.array(view.pipe)))
        fitting = Line.fit(scale.to_mm(np.array(view.fitting)))
        return AlignSample(frame_index, angle_between(pipe, fitting), view.confidence, scale.quality)

    def series(self, samples: list[AlignSample]) -> dict[tuple[str, str], list[float]]:
        return {("angle_deg", "misalignment between pipe and fitting axes"): [s.angle_deg for s in samples]}
