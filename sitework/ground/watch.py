"""Amendment and recall watch: Tavily Research findings become gated `policy.update` proposals.

Research text is data. The gate sees only structured facts (kind, scene, URL, domain, date and a
hash of each title); a named person resolves the proposal.
"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError

from sitework.ground.packs import Pack
from sitework.ground.web import WebClient, allowed

# Tavily Research accepts only `properties` and `required` at the top level of an output schema.
SCHEMA = {
    "properties": {
        "findings": {
            "type": "array",
            "description": "Each amendment, recall or new official guidance found; empty if none.",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["amendment", "recall", "new_guidance"]},
                    "scene": {"type": "string", "enum": ["decking", "trench", "plumbing"]},
                    "title": {"type": "string", "description": "Official title or identifier, e.g. AFS 2025:6."},
                    "effective_date": {"type": "string", "description": "ISO date it takes effect, if stated."},
                    "source_url": {"type": "string", "description": "URL of the official source."},
                },
                "required": ["kind", "scene", "title", "source_url"],
            },
        }
    },
    "required": ["findings"],
}


class Finding(BaseModel):
    kind: Literal["amendment", "recall", "new_guidance"]
    scene: Literal["decking", "trench", "plumbing"]
    title: str
    source_url: str
    effective_date: str = ""
    allowlisted: bool = False

    @property
    def source_domain(self) -> str:
        return urlparse(self.source_url).netloc.lower()

    def fact(self) -> dict:
        """What may reach the gate: no free text, only structure and a hash of the title."""
        return {"kind": self.kind, "scene": self.scene, "source_url": self.source_url,
                "source_domain": self.source_domain, "allowlisted": self.allowlisted,
                "effective_date": self.effective_date,
                "title_sha256": hashlib.sha256(self.title.encode()).hexdigest()}


class Proposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    jurisdiction: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str
    question: str
    findings: list[Finding]
    cited: list[str]  # every URL Tavily cited, allowlisted or not
    result_sha256: str
    exchange: dict | None = None  # gate Exchange as JSON
    status: Literal["pending", "approved", "rejected"] = "pending"
    resolved_by: str = ""
    resolved_at: datetime | None = None
    note: str = ""


class ProposalStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def save(self, proposal: Proposal) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{proposal.id}.json"
        path.write_text(proposal.model_dump_json(indent=1))
        return path

    def get(self, proposal_id: str) -> Proposal | None:
        path = self.directory / f"{proposal_id}.json"
        return Proposal.model_validate_json(path.read_text()) if path.exists() else None

    def all(self) -> list[Proposal]:
        files = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [Proposal.model_validate_json(p.read_text()) for p in files]


class AmendmentWatch:
    """One Tavily Research task per jurisdiction, structured by SCHEMA, checked against the pack allowlist."""

    def __init__(self, web: WebClient | None, pack: Pack):
        self.web = web
        self.pack = pack

    def question(self) -> str:
        domains = sorted({d for ds in self.pack.allowlist.values() for d in ds})
        return (f"Which amendments to the rules in {self.pack.authority or self.pack.jurisdiction}, and which "
                f"product recalls or official installation-guidance changes affecting construction hold points "
                f"(decking, trench excavation, plumbing joints) in {self.pack.jurisdiction}, were published from "
                f"2025 onwards? Cite only official sources such as {', '.join(domains)}.")

    def run(self, timeout: float = 420, poll: float = 10) -> tuple[str, str, dict]:
        question = self.question()
        rid = self.web.research(question, SCHEMA)
        deadline = time.time() + timeout
        while True:
            result = self.web.research_result(rid)
            if result.get("status") in ("completed", "failed") or time.time() > deadline:
                return rid, question, result
            time.sleep(poll)

    def proposal(self, request_id: str, question: str, result: dict) -> Proposal:
        if result.get("status") != "completed":
            raise ValueError(f"research {request_id} ended with status {result.get('status')!r}")
        content = result.get("content")
        content = json.loads(content) if isinstance(content, str) else content or {}
        findings = []
        for raw in content.get("findings", []):
            try:
                f = Finding.model_validate(raw)
            except ValidationError:
                continue
            f.allowlisted = allowed(f.source_domain, self.pack.allowlist.get(f.scene, []))
            findings.append(f)
        digest = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        return Proposal(jurisdiction=self.pack.jurisdiction, request_id=request_id, question=question,
                        findings=findings, cited=[s.get("url", "") for s in result.get("sources", [])],
                        result_sha256=digest)


class PolicyUpdate:
    """Sends a proposal through the gate as `policy.update`, then records a named person's resolution."""

    def __init__(self, gate, store: ProposalStore):
        self.gate = gate
        self.store = store

    def propose(self, proposal: Proposal) -> Proposal:
        facts = [f.fact() for f in proposal.findings]
        exchange = self.gate.propose_intent(
            action={"type": "policy.update", "resource": f"sitework/policy/{proposal.jurisdiction}",
                    "parameters": {"proposal_id": proposal.id, "research_sha256": proposal.result_sha256}},
            context={"sitework_jurisdiction": proposal.jurisdiction,
                     "sitework_findings": len(facts),
                     "sitework_findings_allowlisted": sum(f["allowlisted"] for f in facts),
                     "sitework": {"findings": facts, "research_request_id": proposal.request_id,
                                  "cited_domains": sorted({urlparse(u).netloc.lower() for u in proposal.cited})}},
            endpoint="jurisdiction-pack",
        )
        proposal.exchange = exchange.model_dump(mode="json")
        self.store.save(proposal)
        return proposal

    def resolve(self, proposal_id: str, approve: bool, approver: str, note: str = "") -> Proposal:
        proposal = self.store.get(proposal_id)
        if proposal is None:
            raise ValueError(f"no proposal {proposal_id}")
        if not approver.strip():
            raise ValueError("a resolution needs a named approver")
        if proposal.status != "pending":
            raise ValueError(f"proposal already {proposal.status} by {proposal.resolved_by}")
        if approve and not ((proposal.exchange or {}).get("result") or {}).get("decision"):
            raise ValueError("Decionis never decided this proposal, so it can only be rejected; run the research again")
        proposal.status = "approved" if approve else "rejected"
        proposal.resolved_by, proposal.note = approver.strip(), note
        proposal.resolved_at = datetime.now(timezone.utc)
        self.store.save(proposal)
        return proposal
