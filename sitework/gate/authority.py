"""Proposes an action to the Decionis execution authority and returns its verdict verbatim.

Flow: Agent-Safe Intent v1 binding -> `enforce-and-bind` (verdict, and on ALLOW a single-use
execution token) -> `claim-token` claims that grant -> `finalize-token` reports the release
COMMITTED inside the claim's lease. Only a claimed and finalized ALLOW can turn the light green.
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


RELEASES = ("inspection.release_hold", "trench.authorize_entry", "work.cover_up")  # actions with a physical release


class Exchange(BaseModel):
    """What was asked, what came back, and what SiteWork made of it."""

    correlation_id: str
    request: dict
    response: dict | None = None
    claim_response: dict | None = None
    finalize_response: dict | None = None
    result: Verdict | GateFailure


class AuthorityRequest:
    """Builds the intent binding and the `enforce-and-bind` body for one SiteWork action."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def build(self, bundle: EvidenceBundle, correlation_id: str) -> tuple[dict, dict]:
        """An inspection: the evidence bundle, its flat facts and their checks."""
        facts = Facts(bundle)
        return self.intent(
            action={"type": bundle.action, "resource": f"sitework/{bundle.scene}",
                    "parameters": {"scene": bundle.scene, "condition": bundle.condition,
                                   "evidence_sha256": bundle_sha256(bundle)}},
            context={**facts.flat(),
                     "sitework": {**bundle.model_dump(mode="json"), "summary": facts.summary(),
                                  "checks": facts.checks()}},
            endpoint="stack-light", correlation_id=correlation_id,
        )

    def intent(self, action: dict, context: dict, endpoint: str, correlation_id: str) -> tuple[dict, dict]:
        """Any SiteWork action as an Agent-Safe Intent v1 binding plus the request body."""
        s = self.settings
        producer = IntentProducer(
            s.decionis_org_id, {"id": s.decionis_actor_id, "type": "AI_AGENT", "runtime": "sitework"},
            s.decionis_intent_ttl_s)
        binding = producer.bind(action=action, context=context, idempotency_key=correlation_id,
                                target={"system": "sitework", "operation": action["type"], "endpoint": endpoint})
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
        cid = str(uuid.uuid4())
        return self._send(cid, lambda: self.requests.build(bundle, cid), bundle.errors)

    def propose_intent(self, action: dict, context: dict, endpoint: str, errors: list[str] = ()) -> Exchange:
        """A non-inspection action such as `policy.update`."""
        cid = str(uuid.uuid4())
        return self._send(cid, lambda: self.requests.intent(action, context, endpoint, cid), list(errors))

    def _send(self, cid: str, build, errors: list[str]) -> Exchange:
        try:
            binding, body = build()
        except IntentError as exc:
            return Exchange(correlation_id=cid, request={},
                            result=GateFailure(error=f"intent refused: {exc}", latency_ms=0.0))
        start = time.perf_counter()
        probe = self.client.post(self.settings.decionis_gate_route, body)
        latency = round((time.perf_counter() - start) * 1000, 1)
        response = probe.body if isinstance(probe.body, dict) else None
        result = self.interpret(probe, latency)
        claim = finalize = None
        if isinstance(result, Verdict) and result.decision == "ALLOW" and result.should_execute:
            action = body["action"]["type"]
            if errors:
                # Interlock: the verdict stays ALLOW verbatim, but SiteWork will not execute an
                # action whose own evidence it knows is incomplete. The grant expires unused.
                result.grant_error = f"not claimed: evidence carries {len(errors)} error(s)"
            elif body.get("mode") != "ENFORCEMENT":
                result.grant_error = f"not claimed: {body.get('mode')} decisions never execute"
            elif action not in RELEASES:
                result.grant_error = f"not claimed: {action} has no release for SiteWork to execute"
            else:
                claim, finalize = self._claim(result, response or {}, binding, body["intent_hash"])
        return Exchange(correlation_id=cid, request=body, response=_redact(response),
                        claim_response=claim, finalize_response=finalize, result=result)

    def _claim(self, verdict: Verdict, response: dict, binding: dict, digest: str) -> tuple[dict | None, dict | None]:
        """Claim the grant, then report the release committed while the claim's lease is live.

        The release is SiteWork's own state change (the hold opens and the light turns green), so
        it is complete once the claim succeeds. An unfinalized claim goes INDETERMINATE when its
        lease expires, and Decionis then refuses every later claim on the same target
        (CURRENT_STATE_UNRESOLVED) until an operator reconciles it.
        """
        token = response.get("execution_token")
        if not token:
            verdict.grant_error = "ALLOW without an execution_token"
            return None, None
        correlation = binding["intent_id"]
        probe = self.client.post(self.settings.decionis_claim_route,
                                 {"execution_token": token, "intent_hash": digest, "intent": binding,
                                  "consumed_by": binding["actor"]["id"], "commit_correlation_id": correlation})
        claim = probe.body if isinstance(probe.body, dict) else None
        verdict.grant_claimed = probe.status == 200 and bool(claim) and claim.get("valid") is True
        if not verdict.grant_claimed:
            reasons = (claim or {}).get("reason_codes") or (claim or {}).get("message") or probe.error
            verdict.grant_error = f"grant not claimed: {probe.status} {reasons}"
            return claim, None
        probe = self.client.post(self.settings.decionis_finalize_route,
                                 {"execution_token": token, "claim_token": claim.get("claim_token"),
                                  "outcome": "COMMITTED", "commit_correlation_id": correlation})
        final = probe.body if isinstance(probe.body, dict) else None
        verdict.grant_finalized = probe.status == 200 and bool(final) and final.get("finalized") is True
        if not verdict.grant_finalized:
            reasons = (final or {}).get("reason_codes") or (final or {}).get("message") or probe.error
            verdict.grant_error = (f"release not finalized: {probe.status} {reasons}; this target needs "
                                   "reconciling in Decionis before its next claim")
        return claim, final

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
        cid = str(uuid.uuid4())
        return self._answer(cid, lambda: self.requests.build(bundle, cid))

    def propose_intent(self, action: dict, context: dict, endpoint: str, errors: list[str] = ()) -> Exchange:
        cid = str(uuid.uuid4())
        return self._answer(cid, lambda: self.requests.intent(action, context, endpoint, cid))

    def _answer(self, cid: str, build) -> Exchange:
        allow = self.decision == "ALLOW"
        verdict = Verdict(decision=self.decision, reason="MOCK GATE", dossier_id=f"mock-{cid}",
                          should_execute=allow, grant_claimed=allow, grant_finalized=allow, latency_ms=0.0)
        try:
            request = build()[1]
        except IntentError as exc:
            request = {"refused": str(exc)}
        return Exchange(correlation_id=cid, request=request, result=verdict)


def _redact(response: dict | None) -> dict | None:
    """Stored records keep everything except the single-use execution token itself."""
    if not response or "execution_token" not in response:
        return response
    return {**response, "execution_token": "<redacted>" if response["execution_token"] else None}


def make_gate(settings: Settings) -> Gate | MockGate:
    return MockGate(settings) if settings.decionis_mode == "mock" else Gate(settings)
