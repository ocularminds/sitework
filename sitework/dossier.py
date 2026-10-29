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
    resolution: dict | None = None  # named human resolution of an ESCALATE (P3)

    @classmethod
    def of(cls, evidence: EvidenceBundle, exchange: Exchange, jurisdiction: str, gate_mode: str) -> "DossierRecord":
        result = exchange.result
        rid = result.dossier_id if isinstance(result, Verdict) and result.dossier_id else \
            f"no-decision-{exchange.correlation_id}"
        return cls(id=rid, jurisdiction=jurisdiction, gate_mode=gate_mode, evidence=evidence, exchange=exchange)

    @property
    def failed(self) -> bool:
        return isinstance(self.exchange.result, GateFailure)


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

    def recent(self, limit: int = 20) -> list[DossierRecord]:
        files = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [DossierRecord.model_validate_json(p.read_text()) for p in files[:limit]]
