"""Capture: frames from a webcam or replayed clip, and audio from a microphone or a clip's track."""

import hashlib
import io
import subprocess
import threading
import time
import wave
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

    BACKTRACK = 5  # frames to step back when the decoder cannot seek to a sampled frame

    def __init__(self, path: Path):
        self.path = Path(path)
        self.label = f"file:{self.path.name}"
        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            raise ValueError(f"cannot open video {self.path}")
        self._count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._lock = threading.Lock()
        self._closed = False

    def grab(self) -> Frame:
        with self._lock:
            if self._closed:
                raise ValueError(f"{self.label} is closed")
            ok, image = self._cap.read()
            if not ok:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, image = self._cap.read()
            if not ok:
                raise ValueError(f"no frames in {self.path}")
            return Frame(image, int(self._cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1)

    def sample(self, count: int) -> list[Frame]:
        """Evenly spaced frames across the clip, so the result does not depend on playback.

        Some phone clips decode their last frame in playback but not after a seek, so a sampled
        frame that will not read is replaced by the nearest earlier one that does. A frame that
        still will not read is an error, never a silently shorter sample."""
        with self._lock:
            if self._closed:
                raise ValueError(f"{self.label} is closed")
            indices = np.linspace(0, max(self._count - 1, 0), num=max(count, 1)).astype(int)
            frames = []
            for i in dict.fromkeys(indices.tolist()):
                floor = max(i - self.BACKTRACK, frames[-1].index + 1 if frames else 0)
                frame = next((f for j in range(i, floor - 1, -1) if (f := self._read(j))), None)
                if frame is None:
                    raise ValueError(f"cannot read frame {i} of {self.path.name} (tried back to frame {floor})")
                frames.append(frame)
            return frames

    def _read(self, index: int) -> Frame | None:
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = self._cap.read()
        return Frame(image, index) if ok else None

    def close(self) -> None:
        # OpenCV releases the GIL during reads; releasing the decoder concurrently can crash it.
        with self._lock:
            if not self._closed:
                self._closed = True
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
        self._closed = False

    def grab(self) -> Frame:
        with self._lock:
            if self._closed:
                raise ValueError(f"{self.label} is closed")
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
        # A preview request may still be inside the native capture delegate when sources change.
        with self._lock:
            if not self._closed:
                self._closed = True
                self._cap.release()


def open_source(spec: str) -> Source:
    """`"0"` or `"camera:0"` opens a webcam; anything else is a video file path."""
    device = spec.removeprefix("camera:")
    return CameraSource(int(device)) if device.isdigit() else FileSource(Path(spec))


@dataclass
class AudioClip:
    """Mono audio around the join. Its hash covers the exact WAV bytes the audio model hears."""

    samples: np.ndarray  # float32, -1..1
    rate: int
    label: str

    @property
    def seconds(self) -> float:
        return len(self.samples) / self.rate

    @cached_property
    def wav(self) -> bytes:
        pcm = (np.clip(self.samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(pcm)
        return buf.getvalue()

    @cached_property
    def sha256(self) -> str:
        return hashlib.sha256(self.wav).hexdigest()


class AudioSource(ABC):
    label: str

    @abstractmethod
    def record(self, seconds: float) -> AudioClip: ...


class FileAudio(AudioSource):
    """The audio track of a recorded clip (phone video or WAV), mono 16 kHz via ffmpeg, capped at 10 s."""

    RATE = 16000
    MAX_SECONDS = 10.0

    def __init__(self, path: Path):
        self.path = Path(path)
        self.label = f"file:{self.path.name}"

    def record(self, seconds: float) -> AudioClip:
        try:
            out = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-i", str(self.path), "-vn", "-ac", "1", "-ar", str(self.RATE),
                 "-t", str(self.MAX_SECONDS), "-f", "s16le", "-"], check=False, capture_output=True)
        except OSError as exc:  # ffmpeg not installed: missing evidence, so the inspection escalates
            raise ValueError(f"cannot read audio from {self.path.name}: ffmpeg unavailable ({exc})") from exc
        if not out.stdout:  # missing file, no audio stream, or an unreadable container
            raise ValueError(f"no audio track in {self.path.name}")
        samples = np.frombuffer(out.stdout, dtype="<i2").astype(np.float32) / 32768.0
        return AudioClip(samples, self.RATE, self.label)


class MicAudio(AudioSource):
    """A live microphone; records while the joint is pushed home."""

    RATE = 16000

    def __init__(self, device: int | None = None):
        self.device = device
        self.label = f"mic:{device if device is not None else 'default'}"

    def record(self, seconds: float) -> AudioClip:
        try:
            import sounddevice as sd
        except OSError as exc:  # PortAudio missing
            raise ValueError(f"microphone unavailable: {exc}") from exc
        try:
            data = sd.rec(int(seconds * self.RATE), samplerate=self.RATE, channels=1, dtype="float32",
                          device=self.device)
            sd.wait()
        except Exception as exc:  # PortAudioError and device errors
            raise ValueError(f"{self.label}: {exc}") from exc
        return AudioClip(data[:, 0].copy(), self.RATE, self.label)


def open_audio(spec: str, video_spec: str = "") -> AudioSource:
    """`"mic"` / `"mic:1"` records live; a path reads a file; empty follows a replayed video's own track."""
    spec = spec or ("" if video_spec.removeprefix("camera:").isdigit() else video_spec)
    if not spec:
        return MicAudio()
    if spec == "mic" or spec.startswith("mic:"):
        device = spec.removeprefix("mic").lstrip(":")
        return MicAudio(int(device) if device.isdigit() else None)
    return FileAudio(Path(spec))
