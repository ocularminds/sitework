"""Nemotron VL on Token Factory: an image in, schema-validated coordinates out."""

import base64
import json
import re
from typing import TypeVar

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from sitework.capture import Frame
from sitework.perceive.views import View

V = TypeVar("V", bound=View)


class VisionError(RuntimeError):
    """The model gave no valid reply after the allowed retry."""


class VisionModel:
    """Asks for JSON coordinates, validates them strictly, and retries once on a bad reply."""

    def __init__(self, client: OpenAI, model: str, max_tokens: int = 800):
        if not model:
            raise VisionError("no vision model ID configured (nebius_vlm_model)")
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    def locate(self, frame: Frame, schema: type[V]) -> V:
        width, height = frame.size
        prompt = schema.PROMPT.format(width=width, height=height)
        image = f"data:image/jpeg;base64,{base64.b64encode(frame.jpeg).decode()}"
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": image}},
            {"type": "text", "text": prompt},
        ]}]
        problem = ""
        for _attempt in range(2):
            if problem:
                messages = [*messages, {"role": "user", "content": (
                    f"Your last reply was rejected: {problem}. Reply again with JSON only, "
                    "in exactly the requested shape.")}]
            try:
                reply = self.client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=self.max_tokens, temperature=0)
            except OpenAIError as exc:
                raise VisionError(f"{type(exc).__name__}: {exc}") from exc
            text = reply.choices[0].message.content or ""
            try:
                view = schema.model_validate(parse_json(text))
            except (ValueError, ValidationError) as exc:
                problem = _short(exc)
                continue
            if view.within(width, height):
                return view
            problem = f"some points fall outside the {width}x{height} image"
        raise VisionError(f"invalid reply after retry: {problem}")


def parse_json(text: str) -> dict:
    """The first JSON object in a reply, tolerating code fences and surrounding prose."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not candidate:
        raise ValueError("no JSON object in reply")
    data = json.loads(candidate)
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    return data


def _short(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        return f"{'.'.join(map(str, first['loc'])) or 'reply'}: {first['msg']}"
    return str(exc)[:200]
