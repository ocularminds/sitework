"""Inspection flows: capture -> fiducial -> model points -> measurement -> citations -> gate -> dossier."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pydantic import BaseModel

from sitework.capture import Frame, Source
from sitework.config import MissingCredential, Settings
from sitework.dossier import DossierRecord, DossierStore
from sitework.gate.authority import Gate, GateFailure, MockGate
from sitework.gate.evidence import EvidenceBuilder, Facts
from sitework.ground.packs import PackStore
from sitework.light import LightState
from sitework.measure.deck import DeckMeasurer
from sitework.measure.fiducial import Fiducial, Scale
from sitework.nebius import TokenFactory
from sitework.perceive.views import DeckingView
from sitework.perceive.vlm import VisionError, VisionModel
from sitework.schema import Action, Citation, Condition, Measurement, Verdict


class Overlay(BaseModel):
    """What the dashboard draws over the inspected frame (all pixel coordinates)."""

    frame_jpeg: str  # base64
    width: int
    height: int
    marker: list[list[float]] = []
    boards: list[list[list[list[float]]]] = []

    @classmethod
    def of(cls, frame: Frame, scale: Scale | None = None, view: DeckingView | None = None) -> "Overlay":
        w, h = frame.size
        return cls(frame_jpeg=base64.b64encode(frame.jpeg).decode(), width=w, height=h,
                   marker=scale.corners_px.tolist() if scale is not None else [],
                   boards=[b.edges for b in view.boards] if view is not None else [])


class InspectionResult(BaseModel):
    record_id: str
    created_at: datetime
    scene: str
    action: str
    condition: str
    jurisdiction: str
    gate_mode: str
    measurements: list[Measurement]
    citations: list[Citation]
    checks: list[dict]
    errors: list[str]
    verdict: Verdict | None
    failure: GateFailure | None
    light: LightState
    overlay: Overlay | None


class DeckingInspection:
    """The decking hold point: board gaps and alignment against an approved requirement."""

    scene = "decking"

    def __init__(self, settings: Settings, gate: Gate | MockGate, store: DossierStore,
                 packs: PackStore, vision: VisionModel | None = None, fiducial: Fiducial | None = None):
        self.settings = settings
        self.gate = gate
        self.store = store
        self.packs = packs
        self.vision = vision
        self.fiducial = fiducial or Fiducial(settings.fiducial_mm)
        self.measurer = DeckMeasurer()

    def run(self, source: Source | None, condition: Condition, jurisdiction: str,
            action: Action = "inspection.release_hold") -> InspectionResult:
        ev = EvidenceBuilder(self.scene, action, condition)
        frames = self._capture(source, ev)
        vision = self._vision(ev)
        scales = {f.index: self.fiducial.detect(f.image) for f in frames}
        for f in frames:
            if scales[f.index] is None:
                ev.error(f"fiducial[{f.index}]", "ArUco DICT_4X4_50 marker not found")
        measurable = [f for f in frames if scales[f.index] is not None]
        views = self._locate(vision, measurable, ev)
        samples, overlay = [], None
        if measurable:
            overlay = Overlay.of(measurable[0], scales[measurable[0].index])
        elif frames:
            overlay = Overlay.of(frames[0])
        for f in measurable:
            view = views.get(f.index)
            if view is None:
                continue
            try:
                samples.append(self.measurer.sample(view, scales[f.index], f.index))
            except ValueError as exc:
                ev.error(f"measure[{f.index}]", exc)
                continue
            if not overlay or not overlay.boards:
                overlay = Overlay.of(f, scales[f.index], view)
        if vision is not None:
            ev.models["vlm"] = vision.model
        ev.measurements = self.measurer.combine(samples, "nemotron-vl edge points + fiducial homography")
        ev.citations = self.packs.load(jurisdiction).citations(self.scene)
        if not ev.citations:
            ev.error("grounding", f"no approved {self.scene} requirement in the {jurisdiction} pack")
        bundle = ev.build()
        exchange = self.gate.propose(bundle)
        record = DossierRecord.of(bundle, exchange, jurisdiction, self.gate.mode)
        self.store.save(record)
        result = exchange.result
        return InspectionResult(
            record_id=record.id, created_at=record.created_at, scene=self.scene, action=action,
            condition=condition, jurisdiction=jurisdiction, gate_mode=self.gate.mode,
            measurements=bundle.measurements, citations=bundle.citations, checks=Facts(bundle).checks(),
            errors=bundle.errors, verdict=result if isinstance(result, Verdict) else None,
            failure=result if isinstance(result, GateFailure) else None,
            light=LightState.of(result), overlay=overlay,
        )

    def _capture(self, source: Source | None, ev: EvidenceBuilder) -> list[Frame]:
        if source is None:
            ev.error("capture", "no video source is open")
            return []
        try:
            frames = source.sample(self.settings.sitework_samples)
        except ValueError as exc:
            ev.error("capture", exc)
            return []
        if not frames:
            ev.error("capture", f"{source.label} returned no frames")
        ev.frames = [f.sha256 for f in frames]
        return frames

    def _vision(self, ev: EvidenceBuilder) -> VisionModel | None:
        if self.vision is not None:
            return self.vision
        try:
            return VisionModel(TokenFactory(self.settings).client, self.settings.nebius_vlm_model)
        except (MissingCredential, VisionError) as exc:
            ev.error("vision", exc)
            return None

    @staticmethod
    def _locate(vision: VisionModel | None, frames: list[Frame], ev: EvidenceBuilder) -> dict[int, DeckingView]:
        if vision is None or not frames:
            return {}
        views = {}
        with ThreadPoolExecutor(max_workers=len(frames)) as pool:
            futures = {f.index: pool.submit(vision.locate, f, DeckingView) for f in frames}
            for index, future in futures.items():
                try:
                    views[index] = future.result()
                except VisionError as exc:
                    ev.error(f"vision[{index}]", exc)
        return views

