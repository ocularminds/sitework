"""Inspection flows: capture -> fiducial -> model points -> measurement -> citations -> gate -> dossier."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel

from sitework.capture import AudioSource, Frame, Source
from sitework.config import MissingCredential, Settings
from sitework.dossier import DossierRecord, DossierStore, Resolution
from sitework.gate.authority import Gate, GateFailure, MockGate
from sitework.gate.evidence import EvidenceBuilder, Facts
from sitework.ground.packs import PackStore
from sitework.light import LightState
from sitework.measure.align import AlignmentMeasurer
from sitework.measure.base import Measurer
from sitework.measure.deck import DeckMeasurer
from sitework.measure.fiducial import Fiducial, Scale
from sitework.measure.snap import EdgeSnapper
from sitework.measure.trench import TrenchMeasurer
from sitework.nebius import TokenFactory
from sitework.perceive.audio import AudioError, AudioModel, DspReport, SeatDsp
from sitework.perceive.views import DeckingView, PlumbingView, TrenchView, View
from sitework.perceive.vlm import VisionError, VisionModel
from sitework.schema import Action, Citation, Condition, EvidenceBundle, Measurement, Verdict


class Overlay(BaseModel):
    """What the dashboard draws over the inspected frame (all pixel coordinates)."""

    frame_jpeg: str  # base64
    width: int
    height: int
    marker: list[list[float]] = []
    segments: list[list[list[float]]] = []

    @classmethod
    def of(cls, frame: Frame, scale: Scale | None = None, segments: list | tuple = ()) -> "Overlay":
        w, h = frame.size
        return cls(frame_jpeg=base64.b64encode(frame.jpeg).decode(), width=w, height=h,
                   marker=scale.corners_px.tolist() if scale is not None else [],
                   segments=[[list(map(float, p)) for p in seg] for seg in segments])


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
    regrounded_from: str | None = None
    resolution: Resolution | None = None


class Inspection:
    """One hold point. Subclasses name the scene, the model view, the measurer and the action."""

    scene: ClassVar[str]
    view: ClassVar[type[View]]
    action: ClassVar[Action]
    method: ClassVar[str]
    required: ClassVar[tuple[str, ...]] = ()  # measurement kinds an approved requirement must bound

    def __init__(self, settings: Settings, gate: Gate | MockGate, store: DossierStore,
                 packs: PackStore, vision: VisionModel | None = None, fiducial: Fiducial | None = None):
        self.settings = settings
        self.gate = gate
        self.store = store
        self.packs = packs
        self.vision = vision
        self.fiducial = fiducial or Fiducial(settings.fiducial_mm, settings.fiducial_id)
        snapper = EdgeSnapper(reach_frac=settings.snap_reach_frac) if settings.snap_edges else None
        self.measurer = self.make_measurer(snapper)

    def make_measurer(self, snapper: EdgeSnapper | None) -> Measurer:
        raise NotImplementedError

    @property
    def measured_by(self) -> str:
        return self.method + (", points snapped to image edges" if self.measurer.snapper else "")

    def run(self, source: Source | None, condition: Condition, jurisdiction: str,
            action: Action | None = None) -> InspectionResult:
        ev = EvidenceBuilder(self.scene, action or self.action, condition)
        heard = self.listen(ev)
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
                sample = self.measurer.sample(view, scales[f.index], f.index, f.image)
            except ValueError as exc:
                ev.error(f"measure[{f.index}]", exc)
                continue
            samples.append(sample)
            if not overlay or not overlay.segments:
                overlay = Overlay.of(f, scales[f.index], sample.segments)
        ev.measurements = self.measurer.combine(samples, self.measured_by) + heard
        ev.citations = self._ground(jurisdiction, ev.errors)
        return self._decide(ev.build(), jurisdiction, overlay)

    def listen(self, ev: EvidenceBuilder) -> list[Measurement]:
        """Measurements by ear, taken before the frames. Scenes without audio take none."""
        return []

    def reground(self, record: DossierRecord, jurisdiction: str) -> InspectionResult:
        """The same evidence decided again against another jurisdiction's approved requirements."""
        old = record.evidence
        errors = [e for e in old.errors if not e.startswith("grounding:")]
        citations = self._ground(jurisdiction, errors)
        bundle = old.model_copy(update={"citations": citations, "errors": errors})
        return self._decide(bundle, jurisdiction, None, regrounded_from=record.id)

    def _ground(self, jurisdiction: str, errors: list[str]) -> list[Citation]:
        citations = self.packs.load(jurisdiction).citations(self.scene)
        if not citations:
            errors.append(f"grounding: no approved {self.scene} requirement in the {jurisdiction} pack")
        bounded = {kind for c in citations for kind in c.threshold}
        for kind in self.required:
            if citations and kind not in bounded:
                errors.append(f"grounding: no approved {jurisdiction} requirement sets a threshold for {kind}")
        return citations

    def _decide(self, bundle: EvidenceBundle, jurisdiction: str, overlay: Overlay | None,
                regrounded_from: str | None = None) -> InspectionResult:
        exchange = self.gate.propose(bundle)
        record = DossierRecord.of(bundle, exchange, jurisdiction, self.gate.mode)
        record.regrounded_from = regrounded_from
        self.store.save(record)
        result = exchange.result
        return InspectionResult(
            record_id=record.id, created_at=record.created_at, scene=self.scene, action=bundle.action,
            condition=bundle.condition, jurisdiction=jurisdiction, gate_mode=self.gate.mode,
            measurements=bundle.measurements, citations=bundle.citations, checks=Facts(bundle).checks(),
            errors=bundle.errors, verdict=result if isinstance(result, Verdict) else None,
            failure=result if isinstance(result, GateFailure) else None,
            light=LightState.of(result), overlay=overlay, regrounded_from=regrounded_from,
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
            s = self.settings
            return VisionModel(TokenFactory(s).client, s.nebius_vlm_model, thinking=s.nebius_vlm_thinking,
                               constrained=s.nebius_vlm_constrained)
        except (MissingCredential, VisionError) as exc:
            ev.error("vision", exc)
            return None

    def _locate(self, vision: VisionModel | None, frames: list[Frame], ev: EvidenceBuilder) -> dict[int, View]:
        if vision is None or not frames:
            return {}
        ev.models["vlm"] = vision.model
        views = {}
        with ThreadPoolExecutor(max_workers=len(frames)) as pool:
            futures = {f.index: pool.submit(vision.locate, f, self.view) for f in frames}
            for index, future in futures.items():
                try:
                    views[index] = future.result()
                except VisionError as exc:
                    ev.error(f"vision[{index}]", exc)
        return views


class DeckingInspection(Inspection):
    """Decking: board gaps and alignment against an approved requirement."""

    scene = "decking"
    view = DeckingView
    action = "inspection.release_hold"
    method = "nemotron-vl board corners + fiducial homography"
    required = ("gap_mm",)

    def make_measurer(self, snapper: EdgeSnapper | None) -> Measurer:
        return DeckMeasurer(snapper)


class TrenchInspection(Inspection):
    """Trench entry: wall slope against the jurisdiction's protective-sloping requirement."""

    scene = "trench"
    view = TrenchView
    action = "trench.authorize_entry"
    method = "nemotron-vl wall points + upright fiducial homography"
    required = ("slope_deg",)

    def make_measurer(self, snapper: EdgeSnapper | None) -> Measurer:
        return TrenchMeasurer(snapper)


class PlumbingInspection(Inspection):
    """Push-fit joint before close-in: seated by ear (DSP, or model and DSP agreeing) and aligned by eye."""

    scene = "plumbing"
    view = PlumbingView
    action = "inspection.release_hold"
    method = "nemotron-vl axis points + fiducial homography"
    required = ("seat_audio", "angle_deg")

    def __init__(self, settings: Settings, gate: Gate | MockGate, store: DossierStore, packs: PackStore,
                 vision: VisionModel | None = None, fiducial: Fiducial | None = None,
                 audio: AudioSource | None = None, audio_model: AudioModel | None = None, dsp: SeatDsp | None = None):
        super().__init__(settings, gate, store, packs, vision, fiducial)
        self.audio = audio
        self.audio_model = audio_model
        self.dsp = dsp or SeatDsp(settings.audio_onset_ratio, settings.audio_centroid_hz)

    def make_measurer(self, snapper: EdgeSnapper | None) -> Measurer:
        return AlignmentMeasurer(snapper)

    def listen(self, ev: EvidenceBuilder) -> list[Measurement]:
        if self.audio is None:
            ev.error("audio", "no audio source is open")
            return []
        try:
            clip = self.audio.record(self.settings.sitework_audio_seconds)
        except ValueError as exc:
            ev.error("audio", exc)
            return []
        ev.audio = clip.sha256
        try:
            dsp = self.dsp.analyse(clip)
        except ValueError as exc:
            ev.error("audio dsp", exc)
            dsp = None
        if self.settings.audio_mode == "dsp":
            return self._dsp_only(dsp, ev)
        model = self._audio_model(ev)
        reply = None
        if model is not None:
            ev.models["audio"] = model.model
            try:
                reply = model.listen(clip)
            except AudioError as exc:
                ev.error("audio model", exc)
        if dsp is None or reply is None:
            return []
        said = "seated" if reply.seated else "not seated"
        heard = "seated" if dsp.seated else "not seated"
        evidence = (f"DSP onset ratio {dsp.onset_ratio} (min {self.dsp.min_ratio}), centroid {dsp.centroid_hz} Hz "
                    f"(min {self.dsp.min_centroid_hz}) at {dsp.onset_s} s")
        if reply.seated != dsp.seated:
            ev.error("audio", f"model says {said} ({reply.confidence:.2f}) but {evidence} says {heard}")
            return []
        return [Measurement(kind="seat_audio", value=reply.seated, confidence=reply.confidence,
                            method=f"{model.model} and {evidence}; both say {said}")]

    def _dsp_only(self, dsp: DspReport | None, ev: EvidenceBuilder) -> list[Measurement]:
        if dsp is None:
            return []
        ev.models["audio"] = "dsp:librosa-onset-strength+spectral-centroid"
        said = "seated" if dsp.seated else "not seated"
        return [Measurement(kind="seat_audio", value=dsp.seated, confidence=dsp.confidence, method=(
            f"DSP onset ratio {dsp.onset_ratio} (min {self.dsp.min_ratio}), centroid {dsp.centroid_hz} Hz "
            f"(min {self.dsp.min_centroid_hz}) at {dsp.onset_s} s; DSP alone says {said}"))]

    def _audio_model(self, ev: EvidenceBuilder) -> AudioModel | None:
        if self.audio_model is not None:
            return self.audio_model
        try:
            return AudioModel(TokenFactory(self.settings).client, self.settings.nebius_audio_model)
        except (MissingCredential, AudioError) as exc:
            ev.error("audio model", f"{exc}; Token Factory rejects input_audio, so a self-hosted audio model "
                                    "is needed (see TODO_HUMAN.md)")
            return None
