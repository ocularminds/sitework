from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from sitework.schema import Citation, EvidenceBundle, Measurement, Verdict


def bundle(**overrides) -> EvidenceBundle:
    data = {
        "scene": "decking",
        "action": "inspection.release_hold",
        "condition": "clean",
        "measurements": [{"kind": "gap_mm", "value": 5.2, "confidence": 0.9, "method": "test"}],
        "citations": [],
        "frame_sha256": ["0" * 64],
        "models": {"vlm": "acme/test"},
        **overrides,
    }
    return EvidenceBundle(**data)


def test_bundle_defaults_to_no_errors_and_no_audio():
    b = bundle()
    assert b.errors == [] and b.audio_sha256 is None


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_outside_unit_interval_is_rejected(confidence):
    with pytest.raises(ValidationError):
        Measurement(kind="gap_mm", value=1.0, confidence=confidence, method="test")


def test_unknown_action_and_condition_are_rejected():
    with pytest.raises(ValidationError):
        bundle(action="inspection.skip")
    with pytest.raises(ValidationError):
        bundle(condition="snow")


def test_verdict_only_accepts_gate_decisions():
    with pytest.raises(ValidationError):
        Verdict(decision="APPROVE", reason="", policy_version="v1", dossier_id="d", latency_ms=1)


def test_citation_round_trips_through_json():
    c = Citation(
        jurisdiction="US-OSHA", requirement="r", threshold={"max_slope_deg": 34},
        url="https://www.osha.gov/x", retrieved_at=datetime.now(timezone.utc),
        content_sha256="a" * 64, source_domain="osha.gov",
    )
    assert Citation.model_validate_json(c.model_dump_json()) == c
