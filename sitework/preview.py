"""Live preview frames for the dashboard: the source image with the calibration marker outlined."""

import cv2
import numpy as np

from sitework.capture import Frame
from sitework.measure.fiducial import Fiducial


class LivePreview:
    """Outlines the printed marker on each preview frame so the operator can frame the work.
    Indicative only: an inspection detects the marker again on the frames it measures."""

    COLOR = (238, 226, 96)  # BGR of the dashboard's marker cyan, #60e2ee

    def __init__(self, fiducial: Fiducial):
        self.fiducial = fiducial

    def jpeg(self, frame: Frame) -> bytes:
        scale = self.fiducial.detect(frame.image)
        if scale is None:
            return frame.jpeg
        image = frame.image.copy()
        cv2.polylines(image, [scale.corners_px.astype(np.int32)], True, self.COLOR, max(2, image.shape[1] // 400))
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes() if ok else frame.jpeg
