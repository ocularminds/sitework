import cv2
import numpy as np

from sitework.capture import Frame
from sitework.measure.fiducial import Fiducial
from sitework.preview import LivePreview
from synth import scene_with_marker


def test_the_live_preview_outlines_the_printed_marker_only():
    preview = LivePreview(Fiducial(40.0, 0))
    marked = Frame(scene_with_marker(), 0)
    drawn = cv2.imdecode(np.frombuffer(preview.jpeg(marked), np.uint8), cv2.IMREAD_COLOR)
    cyan = np.all(np.abs(drawn.astype(int) - LivePreview.COLOR) < 40, axis=2)
    assert cyan.sum() > 200  # the outline is drawn on a copy
    assert not np.all(np.abs(marked.image.astype(int) - LivePreview.COLOR) < 40, axis=2).any()
    blank = Frame(np.full((900, 1400, 3), 255, np.uint8), 0)
    assert preview.jpeg(blank) == blank.jpeg  # no marker, no outline
