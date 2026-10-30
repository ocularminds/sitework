import json
from datetime import datetime, timezone

import httpx
import pytest

from sitework.config import Settings
from sitework.gate.authority import Gate, GateFailure, MockGate
from sitework.gate.decionis import DecionisClient, Probe
from sitework.gate.evidence import Facts, bundle_sha256
from sitework.gate.intent import intent_hash
from sitework.light import LightState
from sitework.schema import Citation, EvidenceBundle, Measurement, Verdict


def settings(**over) -> Settings:
    return Settings(_env_file=None, **{
        "decionis_api_key": "test-workspace-key", "agentsafe_tenant_key": "test-tenant-key",
        "decionis_gateway_url": "https://dci.decionisedge.com", "decionis_org_id": "org-test", **over})


def bundle(**over) -> EvidenceBundle:
    data = {
        "scene": "decking", "action": "inspection.release_hold", "condition": "clean",
        "measurements": [Measurement(kind="gap_mm", value=4.1, confidence=0.9, method="t"),
                         Measurement(kind="gap_mm", value=7.0, confidence=0.9, method="t"),
                         Measurement(kind="angle_deg", value=2.0, confidence=0.8, method="t")],
        "citations": [Citation(jurisdiction="US", requirement="1/8 to 1/4 in side gap",
                               threshold={"gap_mm": {"min": 3.17, "max": 6.35}}, url="https://www.timbertech.com/x",
                               retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc), content_sha256="a" * 64,
                               source_domain="www.timbertech.com")],
        "frame_sha256": ["f" * 64], "models": {"vlm": "acme/vl"}, **over,
    }
    return EvidenceBundle(**data)


def test_facts_compare_measurements_with_cited_thresholds():
    facts = Facts(bundle())
    assert [(c["value"], c["within"]) for c in facts.checks()] == [(4.1, True), (7.0, False)]
    s = facts.summary()
    assert s["checks_outside"] == 1 and s["unchecked_kinds"] == ["angle_deg"] and s["min_confidence"] == 0.8


ORG = "124e5022-6eee-4717-ab65-a03899db6237"


def gate_with(respond, **over):
    cfg = settings(decionis_org_id=ORG, **over)
    return Gate(cfg, DecionisClient(cfg, transport=httpx.MockTransport(respond)))


def allow(**extra):
    return {"status": "ALLOW", "should_execute": True, "reason_codes": ["POLICY_ACTION_AUTO_APPROVE"],
            "dossier_id": "dos_1", "dossier_url": "https://api.decionis.com/v1/x?sig=1", "decision_id": "dec_1",
            "execution_token": "tok_secret", "policy_version": "dci-v3", **extra}


def test_request_is_an_agent_safe_intent_with_a_matching_hash():
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, json={"status": "BLOCK", "should_execute": False, "reason_codes": ["GAP_OUTSIDE"],
                                         "dossier_id": "dos_1", "decision_id": "dec_1"})

    b = bundle()
    exchange = gate_with(respond).propose(b)
    req = sent[0]
    body = json.loads(req.content)
    assert str(req.url) == "https://dci.decionisedge.com/v1/authority/enforce-and-bind"
    assert req.headers["agentsafe-tenant-key"] == "test-tenant-key"
    assert req.headers["authorization"] == "Bearer test-workspace-key"
    assert "idempotency-key" not in req.headers
    binding = {k: v for k, v in body.items() if k not in ("intent_hash", "mode")}
    assert body["intent_hash"] == intent_hash(binding) and body["mode"] == "ENFORCEMENT"
    assert body["protocol_version"] == "agent-safe.intent/1" and body["tenant_id"] == ORG
    assert body["context"]["idempotency_key"] == exchange.correlation_id
    assert body["action"] == {"type": "inspection.release_hold", "resource": "sitework/decking",
                              "parameters": {"scene": "decking", "condition": "clean",
                                             "evidence_sha256": bundle_sha256(b)}}
    assert body["context"]["sitework"]["summary"]["checks_outside"] == 1
    assert "policy_projection" not in body
    v = exchange.result
    assert isinstance(v, Verdict) and v.decision == "BLOCK" and v.reason == "GAP_OUTSIDE" and not v.green
    assert len(sent) == 1  # no claim for a BLOCK


CLAIM_TOKEN = "c" * 43


def claim_then(finalize: httpx.Response, sent: list):
    def respond(request):
        sent.append(request)
        if request.url.path.endswith("/claim-token"):
            return httpx.Response(200, json={"valid": True, "claims": {"decision_id": "dec_1"},
                                             "claim_token": CLAIM_TOKEN})
        if request.url.path.endswith("/finalize-token"):
            return finalize
        return httpx.Response(200, json=allow())
    return respond


def test_allow_is_green_only_after_the_grant_is_claimed_and_the_release_finalized():
    sent = []
    finalized = httpx.Response(200, json={"finalized": True, "outcome": "COMMITTED"})
    exchange = gate_with(claim_then(finalized, sent)).propose(bundle(errors=[]))
    first, claim, final = (json.loads(r.content) for r in sent)
    assert [r.url.path for r in sent[1:]] == ["/v1/execution/claim-token", "/v1/execution/finalize-token"]
    assert claim["execution_token"] == "tok_secret" and claim["intent_hash"] == first["intent_hash"]
    assert claim["intent"]["intent_id"] == first["intent_id"]
    assert claim["consumed_by"] == "sitework-inspector" and claim["commit_correlation_id"] == first["intent_id"]
    assert final == {"execution_token": "tok_secret", "claim_token": CLAIM_TOKEN, "outcome": "COMMITTED",
                     "commit_correlation_id": first["intent_id"]}
    assert exchange.result.grant_claimed and exchange.result.grant_finalized and exchange.result.green
    assert exchange.finalize_response["finalized"] is True
    assert exchange.response["execution_token"] == "<redacted>"


def test_a_release_that_is_not_finalized_keeps_the_light_off_green():
    """An unfinalized claim goes INDETERMINATE and blocks the target's next claim, so say so."""
    refused = httpx.Response(409, json={"finalized": False, "reason_codes": ["CLAIM_LEASE_EXPIRED"]})
    v = gate_with(claim_then(refused, [])).propose(bundle(errors=[])).result
    assert v.grant_claimed and not v.grant_finalized and not v.green
    assert "CLAIM_LEASE_EXPIRED" in v.grant_error and "reconcil" in v.grant_error
    assert LightState.of(v) == LightState(color="red", label="NOT RELEASED")  # never a red "ALLOW" on the phone


def test_a_refused_claim_keeps_the_light_off_green_and_finalizes_nothing():
    sent = []

    def respond(request):
        sent.append(request)
        if request.url.path.endswith("/claim-token"):
            return httpx.Response(409, json={"valid": False, "reason_codes": ["CURRENT_STATE_UNRESOLVED"]})
        return httpx.Response(200, json=allow())

    v = gate_with(respond).propose(bundle()).result
    assert v.decision == "ALLOW" and not v.green and "CURRENT_STATE_UNRESOLVED" in v.grant_error
    assert LightState.of(v).color == "red" and len(sent) == 2


def test_allow_is_claimed_only_for_a_release_in_enforcement():
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, json=allow())

    shadow = gate_with(respond, decionis_gate_mode="SHADOW").propose(bundle(errors=[])).result
    assert len(sent) == 1 and not shadow.grant_claimed and "SHADOW" in shadow.grant_error
    update = gate_with(respond).propose_intent(
        action={"type": "policy.update", "resource": "sitework/policy/SE", "parameters": {"proposal_id": "p"}},
        context={"sitework_jurisdiction": "SE"}, endpoint="jurisdiction-pack").result
    assert len(sent) == 2 and not update.grant_claimed and "policy.update" in update.grant_error
    assert LightState.of(update).color == "red"


def test_allow_on_evidence_with_errors_is_never_claimed():
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, json=allow())

    v = gate_with(respond).propose(bundle(errors=["vision[0]: invalid reply after retry"])).result
    assert len(sent) == 1 and v.decision == "ALLOW" and not v.green and "error" in v.grant_error


def test_missing_org_id_refuses_the_intent_without_a_request():
    def unexpected(request):
        pytest.fail("no request expected")

    cfg = settings(decionis_org_id="")
    result = Gate(cfg, DecionisClient(cfg, transport=httpx.MockTransport(unexpected))).propose(bundle()).result
    assert isinstance(result, GateFailure) and "DECIONIS_ORG_ID" in result.error


@pytest.mark.parametrize("probe,expected", [
    (Probe(url="u", error="ConnectError: refused"), "ConnectError"),
    (Probe(url="u", status=401, body={"code": "TENANT_KEY_MISSING"}), "HTTP 401"),
    (Probe(url="u", status=200, body={"status": "APPROVE", "dossier_id": "d"}), "unexpected status"),
    (Probe(url="u", status=200, body={"status": "ALLOW", "should_execute": True}), "ALLOW without a dossier_id"),
])
def test_anything_but_a_well_formed_decision_is_a_failure(probe, expected):
    result = Gate.interpret(probe, 12.0)
    assert isinstance(result, GateFailure) and expected in result.error
    assert LightState.of(result).color == "red"


@pytest.mark.parametrize("status,execute,color", [
    ("ALLOW", True, "red"), ("ALLOW", False, "red"), ("ESCALATE", False, "amber"),
    ("REVIEW_REQUIRED", False, "amber"), ("BLOCK", False, "red"), ("ERROR", False, "red"),
])
def test_light_is_green_only_for_allow_with_execute(status, execute, color):
    v = Gate.interpret(Probe(url="u", status=200, body={"status": status, "should_execute": execute,
                                                        "dossier_id": "d"}), 1.0)
    assert LightState.of(v).color == color  # ALLOW alone is red until its grant is claimed


def test_missing_credentials_make_no_request():
    cfg = settings(agentsafe_tenant_key=None, decionis_org_id=ORG)

    def unexpected(request):
        pytest.fail("no request expected")

    gate = Gate(cfg, DecionisClient(cfg, transport=httpx.MockTransport(unexpected)))
    assert isinstance(gate.propose(bundle()).result, GateFailure)


def test_decision_type_sets_the_policy_projection_inside_the_hash():
    gate = MockGate(settings(decionis_org_id=ORG, decionis_decision_type="SITEWORK_RELEASE_HOLD"))
    body = gate.propose(bundle()).request
    assert body["policy_projection"] == {"decision_type": "SITEWORK_RELEASE_HOLD", "transaction_type": None,
                                         "workflow_key": None, "channel": None}
    assert body["intent_hash"] == intent_hash({k: v for k, v in body.items() if k not in ("intent_hash", "mode")})
    assert gate.mode == "mock"
