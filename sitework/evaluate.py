"""Evaluation: labelled clips through the full pipeline, scored per condition.

Nothing here invents a number: every figure in a report comes from a scored run over
`eval/labels.csv`. Missing truth is left blank, never guessed.
"""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from sitework.scenes import InspectionResult
from sitework.schema import Condition

CONDITIONS: list[Condition] = ["clean", "rain", "mud", "dusk_glare", "outdoor"]
COLUMN_TITLES = {"clean": "Clean bench", "rain": "Cosmos rain", "mud": "Cosmos mud",
                 "dusk_glare": "Cosmos dusk/glare", "outdoor": "Outdoor phone"}
Expected = Literal["ALLOW", "BLOCK", "ESCALATE"]


class Label(BaseModel):
    """One row of eval/labels.csv: a clip, how it was made, the truth and the right verdict."""

    clip: str
    scene: Literal["decking", "trench", "plumbing"]
    condition: Condition
    jurisdiction: str = "US"
    gap_min_mm: float | None = None
    gap_max_mm: float | None = None
    angle_deg: float | None = None
    slope_deg: float | None = None
    depth_mm: float | None = None
    seated: bool | None = None
    expected: Expected
    notes: str = ""

    @field_validator("gap_min_mm", "gap_max_mm", "angle_deg", "slope_deg", "depth_mm", "seated", mode="before")
    @classmethod
    def _blank(cls, v):
        return None if v in ("", None) else v


class LabelFile:
    COLUMNS = ["clip", "scene", "condition", "jurisdiction", "gap_min_mm", "gap_max_mm", "angle_deg",
               "slope_deg", "depth_mm", "seated", "expected", "notes"]

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[Label]:
        with self.path.open(newline="") as f:
            reader = csv.DictReader(f)
            missing = set(self.COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{self.path} is missing columns {sorted(missing)}")
            rows = [r for r in reader if any((v or "").strip() for v in r.values())]
        return [Label.model_validate({k: (v or "").strip() for k, v in r.items()}) for r in rows]


class Scored(BaseModel):
    """One clip's outcome against its label."""

    clip: str
    scene: str
    condition: Condition
    jurisdiction: str
    expected: Expected
    decision: str  # Decionis status, or "NO DECISION"
    correct: bool
    false_allow: bool
    escalated: bool
    abs_error: dict[str, float] = Field(default_factory=dict)  # truth column -> |measured - truth|
    seat_correct: bool | None = None
    min_confidence: float | None = None
    latency_ms: float | None = None
    record_id: str
    dossier_id: str = ""
    verified: bool | None = None
    errors: list[str] = Field(default_factory=list)


class Scorer:
    """Compares an inspection with its label. The method text says which gap a measurement is."""

    def score(self, label: Label, result: InspectionResult) -> Scored:
        decision = result.verdict.decision if result.verdict else "NO DECISION"
        errors: dict[str, float] = {}
        seat_correct = None
        for m in result.measurements:
            truth_key = self._truth_key(label.scene, m.kind, m.method)
            truth = getattr(label, truth_key) if truth_key else None
            if truth_key == "seated" and truth is not None:
                seat_correct = bool(m.value) == truth
            elif truth is not None:
                errors[truth_key] = round(abs(float(m.value) - truth), 3)
        confidences = [m.confidence for m in result.measurements]
        return Scored(
            clip=label.clip, scene=label.scene, condition=label.condition, jurisdiction=label.jurisdiction,
            expected=label.expected, decision=decision,
            correct=decision == label.expected or (label.expected == "ESCALATE" and decision == "REVIEW_REQUIRED"),
            false_allow=decision == "ALLOW" and label.expected != "ALLOW",
            escalated=decision in ("ESCALATE", "REVIEW_REQUIRED"),
            abs_error=errors, seat_correct=seat_correct,
            min_confidence=min(confidences) if confidences else None,
            latency_ms=result.verdict.latency_ms if result.verdict else None,
            record_id=result.record_id, dossier_id=result.verdict.dossier_id if result.verdict else "",
            errors=result.errors,
        )

    @staticmethod
    def _truth_key(scene: str, kind: str, method: str) -> str | None:
        if kind == "gap_mm":
            return "gap_min_mm" if "narrowest" in method else "gap_max_mm" if "widest" in method else None
        return {"angle_deg": "angle_deg", "slope_deg": "slope_deg", "depth_mm": "depth_mm",
                "seat_audio": "seated"}.get(kind)


class ConditionStats(BaseModel):
    condition: Condition
    n: int
    gap_error_mm: float | None
    angle_error_deg: float | None
    slope_error_deg: float | None
    depth_error_mm: float | None
    seat_accuracy: float | None
    correct_rate: float
    false_allow_rate: float
    false_allows: int
    escalate_rate: float
    no_decision: int
    suggested_floor: float | None  # lowest floor that would have escalated every false ALLOW here


class Run(BaseModel):
    label: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    commit: str = ""
    gate_mode: str
    decionis_mode: str
    policy_versions: list[str] = Field(default_factory=list)
    models: dict[str, list[str]] = Field(default_factory=dict)
    floors: dict[str, float] = Field(default_factory=dict)  # condition -> floor in the policy file
    rows: list[Scored] = Field(default_factory=list)

    def by_condition(self) -> list[ConditionStats]:
        return [self._stats(c, [r for r in self.rows if r.condition == c]) for c in CONDITIONS
                if any(r.condition == c for r in self.rows)]

    def p95_latency_ms(self) -> float | None:
        values = sorted(r.latency_ms for r in self.rows if r.latency_ms is not None)
        if not values:
            return None
        return values[max(0, math.ceil(0.95 * len(values)) - 1)]  # nearest-rank

    def dossiers(self) -> tuple[int, int, int]:
        """(produced, verified offline, attempted verifications)."""
        produced = [r for r in self.rows if r.dossier_id and not r.dossier_id.startswith("mock-")]
        attempted = [r for r in produced if r.verified is not None]
        return len(produced), sum(bool(r.verified) for r in attempted), len(attempted)

    @staticmethod
    def _stats(condition: Condition, rows: list[Scored]) -> ConditionStats:
        def mean(*keys: str) -> float | None:
            vals = [r.abs_error[k] for r in rows for k in keys if k in r.abs_error]
            return round(sum(vals) / len(vals), 2) if vals else None

        seats = [r.seat_correct for r in rows if r.seat_correct is not None]
        false_allows = [r for r in rows if r.false_allow]
        confs = [r.min_confidence for r in false_allows if r.min_confidence is not None]
        n = len(rows)
        return ConditionStats(
            condition=condition, n=n,
            gap_error_mm=mean("gap_min_mm", "gap_max_mm"), angle_error_deg=mean("angle_deg"),
            slope_error_deg=mean("slope_deg"), depth_error_mm=mean("depth_mm"),
            seat_accuracy=round(sum(seats) / len(seats), 3) if seats else None,
            correct_rate=round(sum(r.correct for r in rows) / n, 3),
            false_allow_rate=round(len(false_allows) / n, 3), false_allows=len(false_allows),
            escalate_rate=round(sum(r.escalated for r in rows) / n, 3),
            no_decision=sum(r.decision == "NO DECISION" for r in rows),
            suggested_floor=round(math.floor(max(confs) * 100) / 100 + 0.01, 2) if confs else None,
        )


class Results(BaseModel):
    """Every run kept, newest last, so a re-run after a floor change is reported beside the first."""

    runs: list[Run] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Results":
        return cls.model_validate_json(path.read_text()) if path.exists() else cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1))


class MarkdownReport:
    """eval/results.md: the brief's Results table per run, then the per-clip detail behind it."""

    def render(self, results: Results) -> str:
        out = ["# SiteWork evaluation", "",
               "Generated by `scripts/eval.py` from `eval/labels.csv`; every number below comes from that run. "
               "Runs are listed newest first and are never overwritten.", ""]
        for run in reversed(results.runs):
            out += self._run(run)
        return "\n".join(out) + "\n"

    def _run(self, run: Run) -> list[str]:
        stats = run.by_condition()
        warn = ["", "> **MOCK GATE.** These verdicts are not from Decionis.", ""] if run.decionis_mode == "mock" else [""]
        models = "; ".join(k + ": " + ", ".join(v) for k, v in run.models.items()) or "—"
        policies = ", ".join(run.policy_versions) or "—"
        head = [f"## {run.label}", *warn,
                f"{run.started_at:%Y-%m-%d %H:%M} UTC · commit `{run.commit or 'unknown'}` · gate mode {run.gate_mode} · "
                f"policy {policies} · models {models}", ""]
        cols = [COLUMN_TITLES[s.condition] + f" (n={s.n})" for s in stats]
        table = ["| Metric | " + " | ".join(cols) + " |", "|---|" + "---|" * len(stats)]
        rows = [
            ("Measurement error (gap mm / angle °)", lambda s: f"{_v(s.gap_error_mm)} / {_v(s.angle_error_deg)}"),
            ("Slope error (°) / depth error (mm)", lambda s: f"{_v(s.slope_error_deg)} / {_v(s.depth_error_mm)}"),
            ("Seat detection accuracy", lambda s: _pct(s.seat_accuracy)),
            ("Correct verdict rate", lambda s: _pct(s.correct_rate)),
            ("**False-ALLOW rate** (target 0)", lambda s: f"**{_pct(s.false_allow_rate)}** ({s.false_allows})"),
            ("ESCALATE rate", lambda s: _pct(s.escalate_rate)),
            ("No decision (gate failure)", lambda s: str(s.no_decision)),
            ("Confidence floor in policy", lambda s: _v(run.floors.get(s.condition))),
        ]
        table += ["| " + name + " | " + " | ".join(fn(s) for s in stats) + " |" for name, fn in rows]
        produced, verified, attempted = run.dossiers()
        p95 = run.p95_latency_ms()
        summary = [f"Gate p95 latency: {_v(p95)} ms (nearest rank, n={sum(r.latency_ms is not None for r in run.rows)}) · "
                   f"Dossiers produced: {produced} · Verified offline: {verified} / {attempted}"]
        floors = [f"- **{COLUMN_TITLES[s.condition]}**: {s.false_allows} false ALLOW(s); raising the floor to "
                  f"{s.suggested_floor} would have escalated them (policy change, needs a person)."
                  for s in stats if s.suggested_floor is not None]
        detail = ["", "<details><summary>Per clip</summary>", "",
                  "| Clip | Scene | Condition | Expected | Decision | Errors (abs) | Min conf | Latency ms | Dossier | Verified |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for r in run.rows:
            errs = ", ".join(f"{k} {v}" for k, v in r.abs_error.items()) or "—"
            detail.append(f"| `{r.clip}` | {r.scene} | {r.condition} | {r.expected} | {r.decision}"
                          f"{' ⚠ false ALLOW' if r.false_allow else ''} | {errs} | {_v(r.min_confidence)} | "
                          f"{_v(r.latency_ms)} | `{r.dossier_id[:8] or '—'}` | {_v(r.verified)} |")
        detail += ["", "</details>", ""]
        return head + table + ["", *summary, *(["", "Floor suggestions:", *floors] if floors else []), *detail]


def _v(x) -> str:
    return "—" if x is None else str(x)


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"
