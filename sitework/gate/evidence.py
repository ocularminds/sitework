"""Evidence bundles and the structured facts derived from them for the gate."""

import hashlib
import json

from sitework.schema import Action, Citation, Condition, EvidenceBundle, Measurement, Scene


class EvidenceBuilder:
    """Collects one inspection's evidence. Problems are recorded, never swallowed."""

    def __init__(self, scene: Scene, action: Action, condition: Condition):
        self.scene, self.action, self.condition = scene, action, condition
        self.measurements: list[Measurement] = []
        self.citations: list[Citation] = []
        self.frames: list[str] = []
        self.audio: str | None = None
        self.models: dict[str, str] = {}
        self.errors: list[str] = []

    def error(self, where: str, problem: object) -> None:
        self.errors.append(f"{where}: {problem}")

    def build(self) -> EvidenceBundle:
        return EvidenceBundle(
            scene=self.scene, action=self.action, condition=self.condition,
            measurements=self.measurements, citations=self.citations, frame_sha256=self.frames,
            audio_sha256=self.audio, models=self.models, errors=self.errors,
        )


class Facts:
    """Deterministic comparisons of measurements against cited thresholds.

    These are measurement facts for the policy to read; the decision stays in Decionis.
    """

    def __init__(self, bundle: EvidenceBundle):
        self.bundle = bundle

    def checks(self) -> list[dict]:
        out = []
        for c in self.bundle.citations:
            for kind, bounds in c.threshold.items():
                for m in self.bundle.measurements:
                    if m.kind != kind or isinstance(m.value, bool):
                        continue
                    lo, hi = bounds.get("min"), bounds.get("max")
                    within = (lo is None or m.value >= lo) and (hi is None or m.value <= hi)
                    out.append({"kind": kind, "value": m.value, "min": lo, "max": hi,
                                "within": within, "confidence": m.confidence, "source": c.url})
        return out

    def summary(self) -> dict:
        checks = self.checks()
        confidences = [m.confidence for m in self.bundle.measurements]
        return {
            "citation_count": len(self.bundle.citations),
            "measurement_count": len(self.bundle.measurements),
            "error_count": len(self.bundle.errors),
            "min_confidence": min(confidences) if confidences else None,
            "checks_total": len(checks),
            "checks_outside": sum(not c["within"] for c in checks),
            "unchecked_kinds": sorted({m.kind for m in self.bundle.measurements} - {c["kind"] for c in checks}),
        }


def bundle_sha256(bundle: EvidenceBundle) -> str:
    """Hash of the canonical bundle JSON (sorted keys), bound into the gate request."""
    canonical = json.dumps(bundle.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
