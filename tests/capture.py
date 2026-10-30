import threading
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytest

from sitework.capture import FileSource, open_source


class SeekLimit:
    """A capture whose decoder cannot return frames from `bad_from` on after a seek, as with the
    last frame of some phone clips."""

    def __init__(self, cap, bad_from: int):
        self.cap, self.bad_from, self.pos = cap, bad_from, 0

    def set(self, prop, value):
        self.pos = int(value)
        return self.cap.set(prop, value)

    def read(self):
        return (False, None) if self.pos >= self.bad_from else self.cap.read()

    def release(self):
        self.cap.release()


@pytest.fixture
def clip(tmp_path):
    """20 flat frames; frame i has intensity 10 * i."""
    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(20):
        writer.write(np.full((48, 64, 3), 10 * i, np.uint8))
    writer.release()
    return path


def test_samples_span_the_whole_clip(clip):
    assert [f.index for f in FileSource(clip).sample(3)] == [0, 9, 19]


def test_a_last_frame_that_will_not_seek_is_replaced_by_the_one_before_it(clip):
    source = FileSource(clip)
    source._cap = SeekLimit(source._cap, bad_from=19)
    frames = source.sample(3)
    assert [f.index for f in frames] == [0, 9, 18]
    assert float(frames[-1].image.mean()) == pytest.approx(180, abs=3)


def test_an_unreadable_stretch_is_an_error_not_a_shorter_sample(clip):
    source = FileSource(clip)
    source._cap = SeekLimit(source._cap, bad_from=10)
    with pytest.raises(ValueError, match="cannot read frame 19"):
        source.sample(3)


@pytest.mark.parametrize("spec", ["camera:0", "bench.mp4"])
@pytest.mark.parametrize("operation", ["grab", "sample"])
def test_closing_a_source_waits_for_native_reads_and_prevents_further_reads(monkeypatch, spec, operation):
    """Changing sources must not destroy a capture while an active preview still uses it."""
    entered, finish, released = threading.Event(), threading.Event(), threading.Event()

    class Capture:
        read_calls = 0
        release_calls = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return 10 if prop == cv2.CAP_PROP_FRAME_COUNT else 1

        def set(self, prop, value):
            return True

        def read(self):
            self.read_calls += 1
            entered.set()
            if not finish.wait(2):
                raise TimeoutError("test did not finish the native read")
            assert not released.is_set(), "capture was destroyed while a read was in progress"
            return True, np.zeros((48, 64, 3), dtype=np.uint8)

        def release(self):
            self.release_calls += 1
            released.set()

    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: capture)
    source = open_source(spec)
    closing_started = threading.Event()

    def close():
        closing_started.set()
        source.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(source.grab if operation == "grab" else lambda: source.sample(1))
        assert entered.wait(1)
        closing = pool.submit(close)
        try:
            assert closing_started.wait(1)
            assert not released.wait(0.1)
        finally:
            finish.set()
        reading.result(timeout=1)
        closing.result(timeout=1)

    assert released.is_set()
    source.close()
    assert capture.release_calls == 1
    with pytest.raises(ValueError, match="closed"):
        source.grab()
    with pytest.raises(ValueError, match="closed"):
        source.sample(1)
    assert capture.read_calls == 1
