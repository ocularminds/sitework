"""Core contracts shared by perception, grounding, the gate and the dossier store."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Scene = Literal["plumbing", "decking", "trench"]
Action = Literal[
    "inspection.release_hold", "trench.authorize_entry", "work.cover_up", "policy.update"
]
Condition = Literal["clean", "rain", "mud", "dusk_glare", "outdoor"]


class Measurement(BaseModel):
    kind: Literal["gap_mm", "angle_deg", "slope_deg", "depth_mm", "seat_audio"]
    value: float | bool
    confidence: float = Field(ge=0.0, le=1.0)
    method: str


class Citation(BaseModel):
    jurisdiction: str
    requirement: str
    threshold: dict
    url: str
    retrieved_at: datetime
    content_sha256: str
    source_domain: str


class EvidenceBundle(BaseModel):
    scene: Scene
    action: Action
    condition: Condition
    measurements: list[Measurement]
    citations: list[Citation]
    frame_sha256: list[str]
    audio_sha256: str | None = None
    models: dict[str, str]
    errors: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    decision: Literal["ALLOW", "ESCALATE", "BLOCK"]
    reason: str
    policy_version: str
    dossier_id: str
    latency_ms: float
