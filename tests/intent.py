import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sitework.gate.intent import IntentError, IntentProducer, canonical_json, intent_hash, iso_ms, js_number

VECTORS = sorted((Path(__file__).parent / "vectors").glob("*.json"))


def cases():
    for path in VECTORS:
        vector = json.loads(path.read_text())
        yield pytest.param(vector, id=path.stem)
        for i, mutation in enumerate(vector.get("mutations", [])):
            yield pytest.param(mutation, id=f"{path.stem}-mutation{i}")


@pytest.mark.parametrize("vector", list(cases()))
def test_published_vectors_reproduce_byte_for_byte(vector):
    assert canonical_json(vector["binding"]) == vector["canonical_json"]
    assert intent_hash(vector["binding"]) == vector["intent_hash"]


def test_every_mutation_has_a_distinct_hash():
    for path in VECTORS:
        vector = json.loads(path.read_text())
        hashes = [vector["intent_hash"]] + [m["intent_hash"] for m in vector.get("mutations", [])]
        assert len(set(hashes)) == len(hashes), path.name


@pytest.mark.parametrize("x,expected", [
    (1.5, "1.5"), (100.0, "100"), (-0.0, "0"), (0.001, "0.001"), (1e-7, "1e-7"), (0.000001, "0.000001"),
    (1e21, "1e+21"), (1e16, "10000000000000000"), (1.2345678901234568e20, "123456789012345680000"),
    (-2.5e-8, "-2.5e-8"), (4.76, "4.76"), (35000, "35000"),
])
def test_numbers_follow_ecmascript(x, expected):
    assert js_number(x) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {"__proto__": 1}, {"a": object()}])
def test_unrepresentable_values_are_refused(bad):
    with pytest.raises(IntentError):
        canonical_json(bad if isinstance(bad, dict) else {"x": bad})


def test_producer_owns_idempotency_expiry_and_tenant():
    p = IntentProducer("00000000-0000-4000-8000-000000000002", {"id": "a", "type": "AI_AGENT"}, ttl_seconds=60)
    t = datetime(2026, 10, 29, 10, 0, 0, 123456, tzinfo=timezone.utc)
    b = p.bind({"type": "inspection.release_hold", "resource": "sitework/decking", "parameters": {}},
               {"sitework": {}}, {"system": "sitework", "operation": "inspection.release_hold"}, "key-1", now=t)
    assert b["captured_at"] == "2026-10-29T10:00:00.123Z" and b["expires_at"] == "2026-10-29T10:01:00.123Z"
    assert b["context"]["idempotency_key"] == "key-1" and b["protocol_version"] == "agent-safe.intent/1"
    with pytest.raises(IntentError, match="idempotency_key"):
        p.bind({}, {"idempotency_key": "agent"}, {}, "k")
    with pytest.raises(IntentError, match="tenant_id"):
        IntentProducer("", {})
    assert iso_ms(t) == "2026-10-29T10:00:00.123Z"
