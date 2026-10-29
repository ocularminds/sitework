import cv2
import numpy as np
import pytest

from sitework.capture import FileSource


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
