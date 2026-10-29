"""Nebius Token Factory client: model catalogue and capability probes."""

import base64
import io
import math
import re
import struct
import wave
from dataclasses import dataclass

from openai import OpenAI, OpenAIError

from sitework.config import Settings


@dataclass(frozen=True)
class Role:
    """A model role and the ID tokens that identify candidates for it."""

    name: str
    required: tuple[str, ...]
    any_of: tuple[str, ...] = ()

    def matches(self, model_id: str) -> bool:
        tokens = [t for t in re.split(r"[^a-z0-9]+", model_id.lower()) if t]

        def has(term: str) -> bool:
            return any(t.startswith(term) for t in tokens)

        return all(has(t) for t in self.required) and (
            not self.any_of or any(has(t) for t in self.any_of)
        )


ROLES = (
    Role("vlm", ("nemotron",), ("vl", "vision")),
    Role("agent", ("nemotron", "super")),
    Role("audio", ("nemotron", "omni")),
)


class ModelCatalog:
    """The model IDs a Token Factory key can call, as returned by `GET /models`."""

    def __init__(self, ids: list[str]):
        self.ids = sorted(set(ids))

    def __len__(self) -> int:
        return len(self.ids)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self.ids

    def candidates(self, role: Role) -> list[str]:
        return [i for i in self.ids if role.matches(i)]


class TokenFactory:
    """OpenAI SDK pointed at Nebius Token Factory."""

    def __init__(self, settings: Settings):
        self._client = OpenAI(
            api_key=settings.secret("nebius_api_key"),
            base_url=settings.nebius_base_url,
            timeout=settings.request_timeout,
        )

    @property
    def client(self) -> OpenAI:
        return self._client

    def catalog(self) -> ModelCatalog:
        return ModelCatalog([m.id for m in self._client.models.list()])

    def accepts_audio(self, model: str) -> tuple[bool, str]:
        """Send a 0.5 s tone as `input_audio` and report whether the API accepts it."""
        clip = base64.b64encode(_tone_wav()).decode()
        try:
            reply = self._client.chat.completions.create(
                model=model,
                max_tokens=16,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this sound in three words."},
                        {"type": "input_audio", "input_audio": {"data": clip, "format": "wav"}},
                    ],
                }],
            )
        except OpenAIError as exc:
            return False, f"{type(exc).__name__}: {exc}"
        return True, (reply.choices[0].message.content or "").strip()


def _tone_wav(seconds: float = 0.5, hz: float = 440.0, rate: int = 16000) -> bytes:
    frames = b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * n / rate)))
        for n in range(int(seconds * rate))
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()
