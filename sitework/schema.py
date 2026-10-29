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


Decision = Literal["ALLOW", "BLOCK", "ESCALATE", "REVIEW_REQUIRED", "ERROR"]


class Verdict(BaseModel):
    """A Decionis authority decision, with its status used verbatim."""

    decision: Decision
    reason: str
    policy_version: str = ""
    dossier_id: str
    latency_ms: float
    should_execute: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    decision_id: str = ""
    dossier_url: str = ""
    grant_claimed: bool = False  # the single-use execution grant was consumed for this intent
    grant_finalized: bool = False  # the release was reported COMMITTED inside the claim's lease
    grant_error: str = ""

    @property
    def green(self) -> bool:
        """The only state that releases a hold: ALLOW, execute, the grant claimed and the release finalized."""
        return self.decision == "ALLOW" and self.should_execute and self.grant_claimed and self.grant_finalized
