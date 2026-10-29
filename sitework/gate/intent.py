"""Agent-Safe Intent v1 producer: the binding SiteWork proposes, its canonical bytes and its hash.

Implements the published profile (github.com/decionis/agent-safe-pipeline, spec/intent/v1):
canonical form = ECMAScript `JSON.stringify` of the value with every object's keys sorted by
UTF-16 code unit; intent hash = "sha256:" + hex SHA-256 of those UTF-8 bytes. The published
conformance vectors under tests/vectors pin this implementation byte for byte.
"""

import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone

PROTOCOL = "agent-safe.intent/1"
MAX_BYTES = 100 * 1024
MAX_DEPTH = 20


class IntentError(ValueError):
    """A binding this producer must refuse rather than repair."""


def canonical_json(value) -> str:
    return _encode(value, 0)


def intent_hash(binding: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def js_number(x) -> str:
    """A number as ECMAScript Number::toString writes it (what JSON.stringify emits)."""
    if isinstance(x, bool):
        raise IntentError("booleans are not numbers")
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        raise IntentError("numbers must be finite")
    if x == 0:
        return "0"  # also -0
    sign = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    whole, _, frac = mantissa.partition(".")
    raw = whole + frac
    stripped = raw.lstrip("0")
    n = len(whole) - (len(raw) - len(stripped)) + (int(exp) if exp else 0)
    digits = stripped.rstrip("0") or "0"
    k = len(digits)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    exponent = ("+" if e >= 0 else "-") + str(abs(e))
    return sign + digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + exponent


def _utf16_key(s: str) -> bytes:
    return s.encode("utf-16-be", "surrogatepass")


def _encode(value, depth: int) -> str:
    if depth > MAX_DEPTH:
        raise IntentError(f"nesting deeper than {MAX_DEPTH}")
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(v, depth + 1) for v in value) + "]"
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise IntentError("object keys must be strings")
            if k in ("__proto__", "constructor", "prototype"):
                raise IntentError(f"key {k!r} is refused")
        items = sorted(value.items(), key=lambda kv: _utf16_key(kv[0]))
        return "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{_encode(v, depth + 1)}"
                              for k, v in items) + "}"
    raise IntentError(f"{type(value).__name__} is not JSON")


def iso_ms(t: datetime) -> str:
    """RFC 3339 UTC with milliseconds and Z, as ECMAScript `toISOString()` writes it."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


class IntentProducer:
    """SiteWork as the trusted producer: it fixes actor, context, target, expiry and retry identity."""

    def __init__(self, tenant_id: str, actor: dict, ttl_seconds: int = 120):
        if not tenant_id:
            raise IntentError("tenant_id (DECIONIS_ORG_ID) is required")
        self.tenant_id = tenant_id
        self.actor = actor
        self.ttl = timedelta(seconds=ttl_seconds)

    def bind(self, action: dict, context: dict, target: dict, idempotency_key: str,
             now: datetime | None = None) -> dict:
        if "idempotency_key" in context:
            raise IntentError("idempotency_key is the producer's and may not be set in context")
        captured = now or datetime.now(timezone.utc)
        binding = {
            "protocol_version": PROTOCOL,
            "tenant_id": self.tenant_id,
            "intent_id": str(uuid.uuid4()),
            "captured_at": iso_ms(captured),
            "expires_at": iso_ms(captured + self.ttl),
            "actor": self.actor,
            "action": action,
            "context": {**context, "idempotency_key": idempotency_key},
            "downstream_target": target,
        }
        size = len(canonical_json(binding).encode("utf-8"))
        if size > MAX_BYTES:
            raise IntentError(f"binding is {size} canonical bytes; the limit is {MAX_BYTES}")
        return binding
