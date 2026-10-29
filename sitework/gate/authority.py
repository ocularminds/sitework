"""Proposes an action to the Decionis execution authority and returns its verdict verbatim.

Flow: Agent-Safe Intent v1 binding -> `enforce-and-bind` (verdict, and on ALLOW a single-use
execution token) -> `consume-token` claims that grant. Only a claimed ALLOW can turn the light green.
"""

import time
import uuid
from typing import get_args

from pydantic import BaseModel

from sitework.config import Settings
from sitework.gate.decionis import DecionisClient, Probe
from sitework.gate.evidence import Facts, bundle_sha256
from sitework.gate.intent import IntentError, IntentProducer, intent_hash
from sitework.schema import Decision, EvidenceBundle, Verdict


class GateFailure(BaseModel):
    """No decision came back. The hold stays closed; this is never shown as a Decionis verdict."""

    error: str
    latency_ms: float
    status: int | None = None


class Exchange(BaseModel):
    """What was asked, what came back, and what SiteWork made of it."""

    correlation_id: str
    request: dict
    response: dict | None = None
    claim_response: dict | None = None
    result: Verdict | GateFailure


class AuthorityRequest:
    """Builds the intent binding and the `enforce-and-bind` body for one SiteWork action."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def build(self, bundle: EvidenceBundle, correlation_id: str) -> tuple[dict, dict]:
        s = self.settings
        producer = IntentProducer(
            s.decionis_org_id, {"id": s.decionis_actor_id, "type": "AI_AGENT", "runtime": "sitework"},
            s.decionis_intent_ttl_s)
        facts = Facts(bundle)
        binding = producer.bind(
            action={"type": bundle.action, "resource": f"sitework/{bundle.scene}",
                    "parameters": {"scene": bundle.scene, "condition": bundle.condition,
                                   "evidence_sha256": bundle_sha256(bundle)}},
            context={"sitework": {**bundle.model_dump(mode="json"), "summary": facts.summary(),
                                  "checks": facts.checks()}},
            target={"system": "sitework", "operation": bundle.action, "endpoint": "stack-light"},
            idempotency_key=correlation_id,
        )
        if s.decionis_decision_type:
            binding["policy_projection"] = {"decision_type": s.decionis_decision_type,
                                            "transaction_type": None, "workflow_key": None, "channel": None}
        return binding, {**binding, "intent_hash": intent_hash(binding), "mode": s.decionis_gate_mode}


class Gate:
    """The live gate. Every irreversible SiteWork action goes through `propose`."""

    mode = "live"

    def __init__(self, settings: Settings, client: DecionisClient | None = None):
        self.settings = settings
        self.client = client or DecionisClient(settings)
        self.requests = AuthorityRequest(settings)

    def propose(self, bundle: EvidenceBundle) -> Exchange:
        correlation_id = str(uuid.uuid4())
        try:
            binding, body = self.requests.build(bundle, correlation_id)
        except IntentError as exc:
            return Exchange(correlation_id=correlation_id, request={},
                            result=GateFailure(error=f"intent refused: {exc}", latency_ms=0.0))
        start = time.perf_counter()
        probe = self.client.post(self.settings.decionis_gate_route, body)
        latency = round((time.perf_counter() - start) * 1000, 1)
        response = probe.body if isinstance(probe.body, dict) else None
        result = self.interpret(probe, latency)
        claim = None
        if isinstance(result, Verdict) and result.decision == "ALLOW" and result.should_execute:
            if bundle.errors:
                # Interlock: the verdict stays ALLOW verbatim, but SiteWork will not execute an
                # action whose own evidence it knows is incomplete. The grant expires unused.
                result.grant_error = f"not claimed: evidence carries {len(bundle.errors)} error(s)"
            else:
                claim = self._claim(result, response or {}, binding, body["intent_hash"])
        return Exchange(correlation_id=correlation_id, request=body, response=_redact(response),
                        claim_response=claim, result=result)

    def _claim(self, verdict: Verdict, response: dict, binding: dict, digest: str) -> dict | None:
        token = response.get("execution_token")
        if not token:
            verdict.grant_error = "ALLOW without an execution_token"
            return None
        probe = self.client.post(self.settings.decionis_claim_route,
                                 {"execution_token": token, "intent_hash": digest, "intent": binding})
        body = probe.body if isinstance(probe.body, dict) else None
        verdict.grant_claimed = probe.status == 200 and bool(body) and body.get("valid") is True
        if not verdict.grant_claimed:
            reasons = (body or {}).get("reason_codes") or (body or {}).get("message") or probe.error
            verdict.grant_error = f"grant not claimed: {probe.status} {reasons}"
        return body

    @staticmethod
    def interpret(probe: Probe, latency_ms: float) -> Verdict | GateFailure:
        if probe.error:
            return GateFailure(error=probe.error, latency_ms=latency_ms)
        body = probe.body if isinstance(probe.body, dict) else {}
        if probe.status is None or probe.status >= 400:
            detail = body.get("message") or body.get("error") or body.get("code") or probe.body
            return GateFailure(error=f"HTTP {probe.status}: {detail}", status=probe.status, latency_ms=latency_ms)
        status = body.get("status")
        if status not in get_args(Decision):
            return GateFailure(error=f"unexpected status {status!r}", status=probe.status, latency_ms=latency_ms)
        dossier = str(body.get("dossier_id") or "")
        if status == "ALLOW" and not dossier:
            return GateFailure(error="ALLOW without a dossier_id", status=probe.status, latency_ms=latency_ms)
        codes = [str(c) for c in body.get("reason_codes") or []]
        return Verdict(
            decision=status, reason=", ".join(codes) or status, reason_codes=codes,
            policy_version=str(body.get("policy_version") or ""), dossier_id=dossier,
            dossier_url=str(body.get("dossier_url") or ""), decision_id=str(body.get("decision_id") or ""),
            should_execute=body.get("should_execute") is True, latency_ms=latency_ms,
        )


class MockGate:
    """Unit tests only (`DECIONIS_MODE=mock`). The dashboard shows a red MOCK GATE banner."""

    mode = "mock"

    def __init__(self, settings: Settings, decision: str = "ESCALATE"):
        self.requests = AuthorityRequest(settings)
        self.decision = decision

    def propose(self, bundle: EvidenceBundle) -> Exchange:
        correlation_id = str(uuid.uuid4())
        allow = self.decision == "ALLOW"
        verdict = Verdict(decision=self.decision, reason="MOCK GATE", dossier_id=f"mock-{correlation_id}",
                          should_execute=allow, grant_claimed=allow, latency_ms=0.0)
        try:
            request = self.requests.build(bundle, correlation_id)[1]
        except IntentError as exc:
            request = {"refused": str(exc)}
        return Exchange(correlation_id=correlation_id, request=request, result=verdict)


def _redact(response: dict | None) -> dict | None:
    """Stored records keep everything except the single-use execution token itself."""
    if not response or "execution_token" not in response:
        return response
    return {**response, "execution_token": "<redacted>" if response["execution_token"] else None}


def make_gate(settings: Settings) -> Gate | MockGate:
    return MockGate(settings) if settings.decionis_mode == "mock" else Gate(settings)
