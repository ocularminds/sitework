"""Nemotron VL on Token Factory: an image in, schema-validated coordinates out."""

import base64
import json
import re
from collections.abc import Callable
from typing import TypeVar

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from sitework.capture import Frame
from sitework.perceive.views import View

V = TypeVar("V", bound=View)
T = TypeVar("T", bound=BaseModel)


class VisionError(RuntimeError):
    """The model gave no valid reply after the allowed retry."""


class StrictJson:
    """One chat request that must come back as JSON in a given schema; one retry with the reason."""

    def __init__(self, client: OpenAI, model: str, max_tokens: int, error: type[Exception],
                 extra: dict | None = None, constrained: bool = False):
        self.client, self.model, self.max_tokens, self.error = client, model, max_tokens, error
        self.extra = extra or {}
        self.constrained = constrained  # ask the server to decode against the schema (json_schema)

    def ask(self, content: list[dict], schema: type[T], check: Callable[[T], str] = lambda _v: "") -> T:
        """`check` returns "" for an acceptable reply, or the reason to reject it."""
        messages = [{"role": "user", "content": content}]
        problem = ""
        for _attempt in range(2):
            if problem:
                messages = [*messages, {"role": "user", "content": (
                    f"Your last reply was rejected: {problem}. Reply again with JSON only, "
                    "in exactly the requested shape.")}]
            try:
                reply = self.client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=self.max_tokens, temperature=0,
                    **self._request_options(schema))
            except OpenAIError as exc:
                raise self.error(f"{type(exc).__name__}: {exc}") from exc
            text = reply.choices[0].message.content or ""
            try:
                value = schema.model_validate(parse_json(text))
            except (ValueError, ValidationError) as exc:
                problem = _short(exc)
                continue
            problem = check(value)
            if not problem:
                return value
        raise self.error(f"invalid reply after retry: {problem}")

    def _request_options(self, schema: type[BaseModel]) -> dict:
        options = dict(self.extra)
        if self.constrained:
            options["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema.__name__.lower(), "schema": schema.model_json_schema(), "strict": True}}
        return options


class VisionModel:
    """Asks for JSON coordinates, validates them strictly, and retries once on a bad reply."""

    def __init__(self, client: OpenAI, model: str, max_tokens: int = 800, thinking: bool = False,
                 constrained: bool = True):
        if not model:
            raise VisionError("no vision model ID configured (nebius_vlm_model)")
        self.model = model
        extra = {} if thinking else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        self.json = StrictJson(client, model, max_tokens, VisionError, extra, constrained)

    def locate(self, frame: Frame, schema: type[V]) -> V:
        width, height = frame.size
        image = f"data:image/jpeg;base64,{base64.b64encode(frame.jpeg).decode()}"
        content = [{"type": "image_url", "image_url": {"url": image}},
                   {"type": "text", "text": schema.PROMPT.format(width=width, height=height)}]
        return self.json.ask(content, schema, lambda v: "" if v.within(width, height) else
                             f"some points fall outside the {width}x{height} image")


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
