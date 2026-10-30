import cv2
import numpy as np
import pytest
from synth import scene_with_marker

from sitework.app import _mjpeg
from sitework.capture import Frame
from sitework.measure.fiducial import Fiducial
from sitework.preview import LivePreview


def test_the_live_preview_outlines_the_printed_marker_only():
    preview = LivePreview(Fiducial(40.0, 0))
    marked = Frame(scene_with_marker(), 0)
    drawn = cv2.imdecode(np.frombuffer(preview.jpeg(marked), np.uint8), cv2.IMREAD_COLOR)
    cyan = np.all(np.abs(drawn.astype(int) - LivePreview.COLOR) < 40, axis=2)
    assert cyan.sum() > 200  # the outline is drawn on a copy
    assert not np.all(np.abs(marked.image.astype(int) - LivePreview.COLOR) < 40, axis=2).any()
    blank = Frame(np.full((900, 1400, 3), 255, np.uint8), 0)
    assert preview.jpeg(blank) == blank.jpeg  # no marker, no outline


def test_preview_keeps_the_source_reference_when_runtime_source_changes():
    class Source:
        def grab(self):
            return Frame(np.zeros((48, 64, 3), dtype=np.uint8), 0)

    class Runtime:
        preview = LivePreview(Fiducial(40.0, 0))
        accesses = 0

        @property
        def source(self):
            self.accesses += 1
            return Source() if self.accesses == 1 else None

    stream = _mjpeg(Runtime(), fps=1000)
    assert b"Content-Type: image/jpeg" in next(stream)
    with pytest.raises(StopIteration):
        next(stream)
