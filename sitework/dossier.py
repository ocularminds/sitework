"""Inspection records: the evidence, the gate exchange and its Decionis dossier reference."""

import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from sitework.gate.authority import Exchange, GateFailure
from sitework.schema import EvidenceBundle, Verdict


class DossierRecord(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    jurisdiction: str
    gate_mode: str
    evidence: EvidenceBundle
    exchange: Exchange
    regrounded_from: str | None = None  # the record whose evidence was re-decided under this jurisdiction
    resolution: "Resolution | None" = None  # named human resolution of an ESCALATE

    @classmethod
    def of(cls, evidence: EvidenceBundle, exchange: Exchange, jurisdiction: str, gate_mode: str) -> "DossierRecord":
        result = exchange.result
        rid = result.dossier_id if isinstance(result, Verdict) and result.dossier_id else \
            f"no-decision-{exchange.correlation_id}"
        return cls(id=rid, jurisdiction=jurisdiction, gate_mode=gate_mode, evidence=evidence, exchange=exchange)

    @property
    def failed(self) -> bool:
        return isinstance(self.exchange.result, GateFailure)


class Resolution(BaseModel):
    """A named person's decision on an escalated hold. It never becomes a Decionis ALLOW."""

    approver: str
    release: bool
    note: str = ""
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    escalated_decision: str
    decionis_approval_request_id: str = ""


DossierRecord.model_rebuild()


class DossierStore:
    """One JSON file per record under `data/dossiers/`."""

    def __init__(self, directory: Path):
        self.directory = directory

    def path(self, record_id: str) -> Path:
        return self.directory / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', record_id)}.json"

    def save(self, record: DossierRecord) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(record.id)
        path.write_text(record.model_dump_json(indent=2))
        return path

    def get(self, record_id: str) -> DossierRecord | None:
        path = self.path(record_id)
        return DossierRecord.model_validate_json(path.read_text()) if path.exists() else None

    def resolve(self, record_id: str, approver: str, release: bool, note: str = "") -> DossierRecord:
        """Record who released or kept an escalated hold. Only ESCALATE / REVIEW_REQUIRED, only once."""
        record = self.get(record_id)
        if record is None:
            raise LookupError(f"no record {record_id}")
        if not approver.strip():
            raise ValueError("a resolution needs a named approver")
        result = record.exchange.result
        if not isinstance(result, Verdict) or result.decision not in ("ESCALATE", "REVIEW_REQUIRED"):
            raise ValueError("only an escalated decision can be resolved by a person")
        if record.resolution is not None:
            raise ValueError(f"already resolved by {record.resolution.approver}")
        response = record.exchange.response or {}
        record.resolution = Resolution(approver=approver.strip(), release=release, note=note,
                                       escalated_decision=result.decision,
                                       decionis_approval_request_id=str(response.get("approval_request_id") or ""))
        self.save(record)
        return record

    def recent(self, limit: int = 20) -> list[DossierRecord]:
        files = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [DossierRecord.model_validate_json(p.read_text()) for p in files[:limit]]
