"""Credential and reachability checks for Token Factory, Tavily and Decionis."""

from abc import ABC, abstractmethod
from base64 import urlsafe_b64decode
import json

from pydantic import BaseModel, Field

from sitework.config import MissingCredential, Settings
from sitework.gate.authority import Gate, GateFailure
from sitework.gate.decionis import DecionisClient
from sitework.ground.web import WebClient
from sitework.nebius import ROLES, TokenFactory
from sitework.schema import EvidenceBundle


class CheckResult(BaseModel):
    """What a check saw (`detail`) and what a human must fix (`blockers`)."""

    name: str
    detail: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers


class Check(ABC):
    """One external dependency. `run` never raises; failures become blockers."""

    name: str

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self) -> CheckResult:
        try:
            return self.probe()
        except MissingCredential as exc:
            return CheckResult(name=self.name, blockers=[str(exc)])
        except Exception as exc:  # report, never crash the doctor
            return CheckResult(name=self.name, blockers=[f"{type(exc).__name__}: {exc}"])

    @abstractmethod
    def probe(self) -> CheckResult: ...


class TokenFactoryCheck(Check):
    """Lists `/models`, resolves each role's exact ID and probes audio input."""

    name = "Nebius Token Factory"

    def __init__(self, settings: Settings, factory: TokenFactory | None = None):
        super().__init__(settings)
        self.factory = factory

    def probe(self) -> CheckResult:
        factory = self.factory or TokenFactory(self.settings)
        catalog = factory.catalog()
        result = CheckResult(name=self.name, detail=[f"{len(catalog)} models listed"])
        for role in ROLES:
            self._resolve(role, catalog, result)
        self._probe_audio(factory, catalog, result)
        return result

    def _resolve(self, role, catalog, result: CheckResult) -> None:
        configured = self.settings.model_for(role.name)
        if configured and configured in catalog:
            result.detail.append(f"{role.name}: {configured} (configured, listed)")
        elif configured:
            result.blockers.append(f"{role.name}: configured ID {configured!r} is not in /models")
        else:
            result.detail.append(f"{role.name}: candidates {catalog.candidates(role) or 'none'}")
            if role.name != "audio":  # audio may fall back to a self-hosted model
                result.blockers.append(
                    f"{role.name}: record the exact ID in sitework/config.py "
                    f"(nebius_{role.name}_model)"
                )

    def _probe_audio(self, factory: TokenFactory, catalog, result: CheckResult) -> None:
        audio = next(r for r in ROLES if r.name == "audio")
        model = self.settings.model_for("audio") or next(iter(catalog.candidates(audio)), "")
        if not model:
            result.detail.append("audio: no Nemotron Omni listed; fallback is Audio Flamingo 3")
            return
        accepted, reply = factory.accepts_audio(model)
        verdict = "accepts input_audio" if accepted else "rejected input_audio"
        result.detail.append(f"audio: {model} {verdict}: {reply[:160]}")


class TavilyCheck(Check):
    """One allowlisted search against OSHA's excavation rule."""

    name = "Tavily"
    query = "OSHA 1926.652 excavation protective systems sloping requirements"
    domains = ["osha.gov", "ecfr.gov"]

    def __init__(self, settings: Settings, web: WebClient | None = None):
        super().__init__(settings)
        self.web = web

    def probe(self) -> CheckResult:
        web = self.web or WebClient(self.settings)
        results = web.search(self.query, self.domains, max_results=3)
        detail = [f"search returned {len(results)} allowlisted results"]
        detail += [f"{r.domain}: {r.url}" for r in results]
        blockers = [] if results else ["search returned no allowlisted results"]
        return CheckResult(name=self.name, detail=detail, blockers=blockers)


class DecionisCheck(Check):
    """Routing, credential scopes and workspace limits for the configured gate mode."""

    name = "Decionis"

    def __init__(self, settings: Settings, client: DecionisClient | None = None):
        super().__init__(settings)
        self.name = f"Decionis ({settings.decionis_gate_mode})"
        self.client = client or DecionisClient(settings)

    def probe(self) -> CheckResult:
        health = self.client.health()
        result = CheckResult(name=self.name)
        result.detail.append(f"health: {health.summary()} {self._version(health)}".rstrip())
        if health.status != 200 or not isinstance(health.body, dict) or health.body.get("ok") is not True:
            result.blockers.append(f"health call failed: {health.summary()}")
        self._check_key(result)
        self._check_gateways(result)
        self._check_workspace_mode(result)
        return result

    def _check_key(self, result: CheckResult) -> None:
        if not self.client.has_key:
            result.blockers.append(f"{self.client.credential_env_var} is not set (see .env.example)")
            return
        if not self.settings.decionis_org_id:
            result.blockers.append("DECIONIS_ORG_ID is not set")
            return
        probe = self.client.key_check()
        accepted = self.client.key_accepted(probe)
        result.detail.append(f"api key: {probe.summary()} ({'accepted' if accepted else 'rejected'})")
        if not accepted:
            result.blockers.append(f"api key not verified for DECIONIS_ORG_ID: {probe.summary()}")
            return
        scopes = probe.body.get("scopes")
        if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
            result.blockers.append("API key scopes are missing or malformed; gate permissions are unverified")
            return
        scopes = [s.strip() for s in scopes]
        mode = self.settings.decionis_gate_mode
        required = {"decision:write", "decision:enforce", "org:*"}
        if mode == "SHADOW":
            required |= {"decision:run", "decision:shadow"}
        permitted = any(s == needed or (s.endswith("*") and needed.startswith(s[:-1]))
                        for s in scopes for needed in required)
        result.detail.append(f"{self.client.credential_env_var}: scopes={', '.join(scopes) or '(none)'}")
        if not permitted:
            result.blockers.append(
                f"{self.client.credential_env_var} cannot run {mode}; "
                f"needs {'decision:shadow or decision:run' if mode == 'SHADOW' else 'decision:enforce'} "
                "or a supported broader decision scope"
            )

    def _check_workspace_mode(self, result: CheckResult) -> None:
        # Readiness metadata comes directly from the authenticated API over TLS.
        # Decoding it here never authorizes an action; the live gate still decides.
        probe = self.client.policy_bundle()
        if probe.status != 200 or not isinstance(probe.body, dict):
            result.blockers.append(f"workspace mode could not be checked: {probe.summary()}")
            return
        try:
            token = probe.body["signed_bundle"]
            if not isinstance(token, str) or len(token.split(".")) != 3:
                raise ValueError("invalid signed_bundle")
            payload = token.split(".")[1]
            claims = json.loads(urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if (not isinstance(claims, dict) or claims.get("aud") != self.settings.decionis_org_id
                    or claims.get("max_mode") not in {"SHADOW", "ENFORCEMENT"}):
                raise ValueError("wrong workspace or unknown max_mode")
        except (KeyError, ValueError, TypeError):
            result.blockers.append("workspace mode claims are missing or malformed")
            return
        maximum = claims["max_mode"]
        reason = claims.get("max_mode_reason")
        result.detail.append(f"workspace max_mode={maximum}" + (f" ({reason})" if reason else ""))
        if self.settings.decionis_gate_mode != "SHADOW" and maximum == "SHADOW":
            result.blockers.append(
                f"workspace refuses {self.settings.decionis_gate_mode}: {reason or 'SHADOW-only'}; "
                "a valid enforcement scope does not lift this workspace restriction"
            )

    def _check_gateways(self, result: CheckResult) -> None:
        probe = self.client.gateway(self.settings.decionis_gateway_url)
        execution = f" ({probe.agentsafe_execution})" if probe.agentsafe_execution else ""
        result.detail.append(f"gateway: {probe.summary()}{execution}")
        routed = (
            probe.status == 200
            and isinstance(probe.body, dict)
            and probe.body.get("ok") is True
            and probe.agentsafe_execution == "PASSTHROUGH"
        )
        if not routed:
            result.blockers.append(f"gateway routing not verified: {probe.summary()}")

    @staticmethod
    def _version(probe) -> str:
        if isinstance(probe.body, dict) and "version" in probe.body:
            return f"(version={probe.body['version']} git_sha={probe.body.get('git_sha')})"
        return ""


class GateCheck(Check):
    """One deliberately incomplete authority request in the configured mode.

    Opt-in (`check.py --gate`): it may write to the Decionis ledger. Its evidence
    carries an error, so Gate never claims an execution grant for this check.
    """

    def __init__(self, settings: Settings, gate: Gate | None = None):
        super().__init__(settings)
        self.name = f"Decionis gate ({settings.decionis_gate_mode})"
        self.gate = gate or Gate(settings)

    def probe(self) -> CheckResult:
        bundle = EvidenceBundle(
            scene="decking", action="inspection.release_hold", condition="clean",
            measurements=[], citations=[], frame_sha256=[], models={},
            errors=["integration check from scripts/check.py --gate: not an inspection"],
        )
        exchange = self.gate.propose(bundle)
        result = CheckResult(name=self.name)
        r = exchange.result
        route = f"{self.settings.decionis_gateway_url}{self.settings.decionis_gate_route}"
        if isinstance(r, GateFailure):
            result.blockers.append(f"{route}: {r.error}")
            if exchange.response:
                result.detail.append(f"response keys: {sorted(exchange.response)}")
            return result
        result.detail.append(f"{route} -> {r.decision} in {r.latency_ms} ms (reason: {r.reason})")
        result.detail.append(f"should_execute={r.should_execute} grant_claimed={r.grant_claimed} "
                             f"{r.grant_error}".rstrip())
        result.detail.append(f"dossier {r.dossier_id or '(none)'}; decision {r.decision_id or '(none)'}")
        result.detail.append(f"response keys: {sorted(exchange.response or {})}")
        if r.decision not in {"ESCALATE", "BLOCK"} or r.should_execute or r.grant_claimed:
            result.blockers.append("incomplete integration evidence must keep the hold closed with ESCALATE or BLOCK")
        return result


class Doctor:
    """Runs every check and reports which external dependencies are usable."""

    def __init__(self, checks: list[Check]):
        self.checks = checks

    @classmethod
    def default(cls, settings: Settings) -> "Doctor":
        return cls([TokenFactoryCheck(settings), TavilyCheck(settings), DecionisCheck(settings)])

    def run(self) -> list[CheckResult]:
        return [check.run() for check in self.checks]
