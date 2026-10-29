"""Joint seating by ear: an audio model's judgement, cross-checked by deterministic DSP.

Neither alone is trusted. The inspection records a seating measurement only when both agree;
a disagreement becomes an error, which the policy escalates to a person.
"""

import base64
from typing import ClassVar

import numpy as np
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from sitework.capture import AudioClip
from sitework.perceive.vlm import StrictJson


class AudioError(RuntimeError):
    """The audio model gave no valid reply after the allowed retry."""


class SeatReply(BaseModel):
    """The audio model's answer: a boolean and a confidence, nothing else."""

    model_config = ConfigDict(extra="forbid")
    seated: bool
    confidence: float = Field(ge=0.0, le=1.0)

    PROMPT: ClassVar[str] = (
        "This is about {seconds:.1f} s of audio recorded at a plumbing joint while a push-fit fitting is "
        "pushed onto a pipe. Did the joint audibly seat, with the distinct click or snap of a fitting "
        "locking home? Reply with JSON only, exactly: {{\"seated\": true or false, \"confidence\": c}} "
        "where c is 0 to 1."
    )


class AudioModel:
    """An audio-capable model on Token Factory (`input_audio`), strictly schema-checked."""

    def __init__(self, client: OpenAI, model: str, max_tokens: int = 100):
        if not model:
            raise AudioError("no audio model ID configured (nebius_audio_model)")
        self.model = model
        self.json = StrictJson(client, model, max_tokens, AudioError)

    def listen(self, clip: AudioClip) -> SeatReply:
        content = [{"type": "input_audio", "input_audio": {"data": base64.b64encode(clip.wav).decode(),
                                                            "format": "wav"}},
                   {"type": "text", "text": SeatReply.PROMPT.format(seconds=clip.seconds)}]
        return self.json.ask(content, SeatReply)


class DspReport(BaseModel):
    onset_s: float  # time of the strongest onset
    onset_ratio: float  # strongest onset strength / median onset strength
    centroid_hz: float  # spectral centroid at that onset
    seated: bool


class SeatDsp:
    """A seat click is a sharp transient with high-frequency energy.

    seated = strongest onset is `min_ratio` times the median onset strength AND its spectral
    centroid is at least `min_centroid_hz`. Both thresholds are starting values to calibrate on
    bench recordings of seated and unseated joints; they are not measured facts.
    """

    def __init__(self, min_ratio: float = 8.0, min_centroid_hz: float = 1500.0):
        self.min_ratio = min_ratio
        self.min_centroid_hz = min_centroid_hz

    def analyse(self, clip: AudioClip) -> DspReport:
        import librosa  # imported lazily: it is slow to load and only plumbing needs it

        y = clip.samples.astype(np.float32)
        if len(y) < clip.rate // 10 or not np.any(y):
            raise ValueError("audio is shorter than 0.1 s or silent")
        envelope = librosa.onset.onset_strength(y=y, sr=clip.rate)
        peak = int(np.argmax(envelope))
        ratio = float(envelope[peak] / (np.median(envelope) + 1e-9))
        centroid = librosa.feature.spectral_centroid(y=y, sr=clip.rate)[0]
        hz = float(centroid[min(peak, len(centroid) - 1)])
        return DspReport(onset_s=round(float(librosa.frames_to_time(peak, sr=clip.rate)), 3),
                         onset_ratio=round(ratio, 2), centroid_hz=round(hz, 1),
                         seated=ratio >= self.min_ratio and hz >= self.min_centroid_hz)
