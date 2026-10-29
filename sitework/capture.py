"""Frame sources: a webcam or a replayed clip. Both hand out hashed frames."""

import hashlib
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Frame:
    """One captured image. Its hash covers the exact JPEG bytes the models see."""

    image: np.ndarray  # BGR
    index: int
    timestamp: float = field(default_factory=time.time)

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.image.shape[:2]
        return w, h

    @cached_property
    def jpeg(self) -> bytes:
        ok, buf = cv2.imencode(".jpg", self.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError("could not encode frame as JPEG")
        return buf.tobytes()

    @cached_property
    def sha256(self) -> str:
        return hashlib.sha256(self.jpeg).hexdigest()


class Source(ABC):
    """Something that yields frames on demand."""

    label: str

    @abstractmethod
    def grab(self) -> Frame: ...

    @abstractmethod
    def sample(self, count: int) -> list[Frame]:
        """`count` frames for one inspection."""

    def close(self) -> None:
        pass


class FileSource(Source):
    """Replays a recorded clip (bench, phone or Cosmos variant), looping for the live view."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.label = f"file:{self.path.name}"
        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            raise ValueError(f"cannot open video {self.path}")
        self._count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._lock = threading.Lock()

    def grab(self) -> Frame:
        with self._lock:
            ok, image = self._cap.read()
            if not ok:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, image = self._cap.read()
            if not ok:
                raise ValueError(f"no frames in {self.path}")
            return Frame(image, int(self._cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1)

    def sample(self, count: int) -> list[Frame]:
        """Evenly spaced frames across the clip, so the result does not depend on playback."""
        with self._lock:
            indices = np.linspace(0, max(self._count - 1, 0), num=max(count, 1)).astype(int)
            frames = []
            for i in dict.fromkeys(indices.tolist()):
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, image = self._cap.read()
                if ok:
                    frames.append(Frame(image, i))
            return frames

    def close(self) -> None:
        self._cap.release()


class CameraSource(Source):
    """A live webcam. Inspection samples are consecutive frames a short interval apart."""

    def __init__(self, device: int, interval: float = 0.2):
        self.label = f"camera:{device}"
        self.interval = interval
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise ValueError(f"cannot open camera {device}")
        self._index = 0
        self._lock = threading.Lock()

    def grab(self) -> Frame:
        with self._lock:
            ok, image = self._cap.read()
            if not ok:
                raise ValueError(f"{self.label} returned no frame")
            self._index += 1
            return Frame(image, self._index)

    def sample(self, count: int) -> list[Frame]:
        frames = []
        for i in range(count):
            if i:
                time.sleep(self.interval)
            frames.append(self.grab())
        return frames

    def close(self) -> None:
        self._cap.release()


def open_source(spec: str) -> Source:
    """`"0"` or `"camera:0"` opens a webcam; anything else is a video file path."""
    device = spec.removeprefix("camera:")
    return CameraSource(int(device)) if device.isdigit() else FileSource(Path(spec))
