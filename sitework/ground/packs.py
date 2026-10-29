"""Jurisdiction packs: per-scene source allowlists and the human-approved requirements read at decision time."""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from sitework.ground.citation import Clause
from sitework.schema import Citation


class Requirement(BaseModel):
    """A clause a named person approved, with the machine-usable threshold they set."""

    scene: str
    requirement: str
    threshold: dict[str, dict[str, float]]  # measurement kind -> {"min": .., "max": ..}
    clause: Clause
    approved_by: str
    approved_at: datetime

    def citation(self, jurisdiction: str) -> Citation:
        c = self.clause
        return Citation(jurisdiction=jurisdiction, requirement=self.requirement, threshold=self.threshold,
                        url=c.url, retrieved_at=c.retrieved_at, content_sha256=c.content_sha256,
                        source_domain=c.source_domain)


class Source(BaseModel):
    """A page the pack was built from: where, when, how, and the hash of the text as read."""

    scene: str
    url: str
    content_sha256: str
    retrieved_at: datetime
    via: str  # "crawl", "map+extract" or "extract"


class Pack(BaseModel):
    jurisdiction: str
    authority: str = ""
    allowlist: dict[str, list[str]] = Field(default_factory=dict)  # scene -> domains
    seeds: dict[str, list[str]] = Field(default_factory=dict)  # scene -> start URLs on the allowlist
    sources: list[Source] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)

    def record(self, source: Source) -> None:
        """Keep one entry per (scene, url): the latest read wins."""
        self.sources = [s for s in self.sources if (s.scene, s.url) != (source.scene, source.url)] + [source]

    def citations(self, scene: str) -> list[Citation]:
        return [r.citation(self.jurisdiction) for r in self.requirements if r.scene == scene]

    def approve(self, scene: str, clause: Clause, requirement: str,
                threshold: dict[str, dict[str, float]], approver: str) -> Requirement:
        if not approver.strip():
            raise ValueError("a requirement needs a named approver")
        domains = self.allowlist.get(scene, [])
        if not any(clause.source_domain == d or clause.source_domain.endswith(f".{d}") for d in domains):
            raise ValueError(f"{clause.source_domain} is not on the {scene} allowlist {domains}")
        for kind, bounds in threshold.items():
            if not bounds or set(bounds) - {"min", "max"}:
                raise ValueError(f"threshold for {kind} must use only 'min' and/or 'max'")
        req = Requirement(scene=scene, requirement=requirement, threshold=threshold, clause=clause,
                          approved_by=approver.strip(), approved_at=datetime.now(timezone.utc))
        self.requirements.append(req)
        return req


class PackStore:
    """Packs on disk at `<dir>/<jurisdiction>.json`."""

    def __init__(self, directory: Path):
        self.directory = directory

    def path(self, jurisdiction: str) -> Path:
        return self.directory / f"{jurisdiction}.json"

    def load(self, jurisdiction: str) -> Pack:
        path = self.path(jurisdiction)
        if not path.exists():
            return Pack(jurisdiction=jurisdiction)
        return Pack.model_validate_json(path.read_text())

    def save(self, pack: Pack) -> Path:
        path = self.path(pack.jurisdiction)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pack.model_dump(mode="json"), indent=2) + "\n")
        return path
