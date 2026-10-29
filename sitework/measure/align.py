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
    point_quality: float
    scale_quality: float
    segments: tuple = ()


class AlignmentMeasurer(Measurer):
    TOLERANCE = {"angle_deg": 0.5}

    def sample(self, view: PlumbingView, scale: Scale, frame_index: int, image: np.ndarray | None = None) -> AlignSample:
        """With snapping, each centre line snaps to a body edge parallel to it; the angle is unchanged."""
        (pipe_px, fitting_px), quality = self.snap_lines(self.snapping(image), [view.pipe, view.fitting], "axis",
                                                         polarity=1)
        quality = view.confidence if quality is None else quality
        pipe = Line.fit(scale.to_mm(np.array(pipe_px)))
        fitting = Line.fit(scale.to_mm(np.array(fitting_px)))
        return AlignSample(frame_index, angle_between(pipe, fitting), quality, scale.quality, (pipe_px, fitting_px))

    def series(self, samples: list[AlignSample]) -> dict[tuple[str, str], list[float]]:
        return {("angle_deg", "misalignment between pipe and fitting axes"): [s.angle_deg for s in samples]}
