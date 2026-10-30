"""FastAPI app: live feed, inspection trigger, verdict push over WebSocket, dossier lookup.

Run with `uvicorn sitework.app:create_app --factory` (or `make demo`).
"""

import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sitework.capture import Source, open_audio, open_source
from sitework.config import ROOT, Settings, get_settings
from sitework.dossier import DossierStore
from sitework.gate.authority import make_gate
from sitework.ground.packs import PackStore
from sitework.ground.watch import PolicyUpdate, ProposalStore
from sitework.light import LightState
from sitework.measure.fiducial import Fiducial
from sitework.preview import LivePreview
from sitework.proof import ProofError, Proofs
from sitework.scenes import DeckingInspection, InspectionResult, PlumbingInspection, TrenchInspection
from sitework.schema import Action, Condition

STATIC = ROOT / "static"


class BrowserAssets(StaticFiles):
    """Revalidate unbundled assets so a deployment cannot leave stale UI modules cached."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


class InspectRequest(BaseModel):
    scene: str = "decking"
    condition: Condition = "clean"
    action: Action | None = None  # None: the scene's own gated action


class SourceRequest(BaseModel):
    spec: str


class ResolveRequest(BaseModel):
    approve: bool
    approver: str
    note: str = ""


class JurisdictionRequest(BaseModel):
    jurisdiction: str
    reground: bool = True


class HoldRequest(BaseModel):
    approver: str
    release: bool
    note: str = ""


class Hub:
    """Fans out JSON messages to every connected dashboard and light page."""

    def __init__(self):
        self.sockets: set[WebSocket] = set()

    async def send(self, message: dict) -> None:
        for ws in list(self.sockets):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self.sockets.discard(ws)


class Runtime:
    """Process-wide state: the open source, the inspection flows and the last result."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gate = make_gate(settings)
        self.store = DossierStore(settings.data_dir / "dossiers")
        self.packs = PackStore(settings.data_dir / "packs")
        self.scenes = {cls.scene: cls(settings, self.gate, self.store, self.packs)
                       for cls in (DeckingInspection, TrenchInspection, PlumbingInspection)}
        self.proofs = Proofs(settings)
        self.proposals = ProposalStore(settings.data_dir / "proposals")
        self.updates = PolicyUpdate(self.gate, self.proposals)
        self.jurisdiction = settings.sitework_jurisdiction
        self.source: Source | None = None
        self.source_error = ""
        self.last: InspectionResult | None = None
        self.lit: str | None = None  # the record the stack light shows; None after the source changes
        self.hub = Hub()
        self.preview = LivePreview(Fiducial(settings.fiducial_mm, settings.fiducial_id))
        self._busy = threading.Lock()
        self.open(settings.sitework_source)

    def open(self, spec: str) -> None:
        """Open the video source; the plumbing microphone follows it unless one is configured."""
        self.scenes["plumbing"].audio = open_audio(self.settings.sitework_audio_source, spec)
        if self.source is not None:
            self.source.close()
        self.lit = None  # a result for the old source says nothing about the work now in view
        try:
            self.source, self.source_error = open_source(spec), ""
        except ValueError as exc:
            self.source, self.source_error = None, str(exc)

    def inspect(self, req: InspectRequest) -> InspectionResult:
        scene = self.scenes.get(req.scene)
        if scene is None:
            raise HTTPException(404, f"scene {req.scene!r} is not built yet")
        if not self._busy.acquire(blocking=False):
            raise HTTPException(409, "an inspection is already running")
        try:
            self.last = scene.run(self.source, req.condition, self.jurisdiction, req.action)
            self.lit = self.last.record_id
            return self.last
        finally:
            self._busy.release()

    def change_source(self, spec: str) -> None:
        """Keep a source change from interrupting evidence capture in another dashboard."""
        if not self._busy.acquire(blocking=False):
            raise HTTPException(409, "an inspection is already running")
        try:
            self.open(spec)
        finally:
            self._busy.release()

    def jurisdictions(self) -> list[str]:
        return sorted(p.stem for p in self.packs.directory.glob("*.json"))

    def switch(self, req: JurisdictionRequest) -> InspectionResult | None:
        """Change the job's jurisdiction; by default re-decide the last inspection under it."""
        if req.jurisdiction not in self.jurisdictions():
            raise HTTPException(404, f"no {req.jurisdiction} pack in {self.packs.directory}")
        if not self._busy.acquire(blocking=False):  # before switching, so a refusal changes nothing
            raise HTTPException(409, "an inspection is already running")
        try:
            self.jurisdiction = req.jurisdiction
            record = self.store.get(self.last.record_id) if (req.reground and self.last) else None
            if record is None:
                return None
            was_lit, frame = self.lit == record.id, self.last.overlay if self.last.record_id == record.id else None
            self.last = self.scenes[record.evidence.scene].reground(record, req.jurisdiction)
            self.last = self.last.model_copy(update={"overlay": frame})  # the same evidence, so the same frame
            self.lit = self.last.record_id if was_lit else None
            return self.last
        finally:
            self._busy.release()

    def hold(self, record_id: str, req: HoldRequest) -> dict:
        """A named person releases or keeps an escalated hold; recorded in the dossier record."""
        try:
            record = self.store.resolve(record_id, req.approver, req.release, req.note)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        light = LightState.resolved(record.resolution.approver, req.release)
        if self.last and self.last.record_id == record_id:
            self.last = self.last.model_copy(update={"light": light, "resolution": record.resolution})
        return {"record_id": record_id, "resolution": record.resolution.model_dump(mode="json"),
                "light": light.model_dump()}

    @staticmethod
    def dossier_id(record_id: str) -> str:
        """Records named after a Decionis dossier can be verified; mock and no-decision records cannot."""
        if record_id.startswith(("mock-", "no-decision-")):
            raise HTTPException(409, "this record has no Decionis dossier to verify")
        return record_id

    def state(self) -> dict:
        return {
            "source": self.source.label if self.source else None,
            "audio": self.scenes["plumbing"].audio.label if self.scenes["plumbing"].audio else None,
            "source_error": self.source_error,
            "gate_mode": self.gate.mode,
            "decision_mode": self.settings.decionis_gate_mode,
            "gateway": self.settings.decionis_gateway_url,
            "gate_route": self.settings.decionis_gate_route,
            "jurisdiction": self.jurisdiction,
            "jurisdictions": self.jurisdictions(),
            "scenes": list(self.scenes),
            "vlm_model": self.settings.nebius_vlm_model,
            "light": (self.last.light if self.last and self.last.record_id == self.lit else LightState.idle()).model_dump(),
            "light_record": self.lit,
            "last": self.last.model_dump(mode="json") if self.last else None,
        }


def create_app(settings: Settings | None = None) -> FastAPI:
    rt = Runtime(settings or get_settings())
    app = FastAPI(title="SiteWork")
    app.state.runtime = rt
    app.mount("/static", BrowserAssets(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/light")
    def light():
        return FileResponse(STATIC / "light.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/state")
    def state():
        return rt.state()

    @app.post("/api/source")
    async def source(req: SourceRequest):
        await run_in_threadpool(rt.change_source, req.spec)
        current = rt.state()
        await rt.hub.send({"type": "state", "state": current})
        return current

    @app.post("/api/inspect")
    async def inspect(req: InspectRequest):
        result = await run_in_threadpool(rt.inspect, req)
        payload = result.model_dump(mode="json")
        await rt.hub.send({"type": "result", "result": payload, "light": payload["light"], "light_record": rt.lit})
        return payload

    @app.get("/api/dossiers/{record_id}")
    def dossier(record_id: str):
        record = rt.store.get(record_id)
        if record is None:
            raise HTTPException(404, "no such record")
        return record.model_dump(mode="json")

    @app.post("/api/jurisdiction")
    async def jurisdiction(req: JurisdictionRequest):
        result = await run_in_threadpool(rt.switch, req)
        if result is not None:
            payload = result.model_dump(mode="json")
            current = rt.state()  # idle light when the re-decided record was not the one lit
            await rt.hub.send({"type": "result", "result": payload, "light": current["light"], "light_record": rt.lit})
        return rt.state()

    @app.post("/api/dossiers/{record_id}/resolve")
    async def hold(record_id: str, req: HoldRequest):
        outcome = rt.hold(record_id, req)
        await rt.hub.send({"type": "resolution", **outcome})
        return outcome

    @app.get("/dossier")
    def dossier_page():
        return FileResponse(STATIC / "dossier.html", headers={"Cache-Control": "no-cache"})

    @app.post("/api/dossiers/{record_id}/verify")
    async def verify(record_id: str, mode: Literal["offline", "pinned"] = "offline"):
        try:
            result = await run_in_threadpool(rt.proofs.verify, rt.dossier_id(record_id), mode)
        except ProofError as exc:
            raise HTTPException(502, str(exc)) from exc
        return result.model_dump(mode="json")

    @app.post("/api/dossiers/{record_id}/tamper")
    async def tamper(record_id: str):
        try:
            result = await run_in_threadpool(rt.proofs.tamper, rt.dossier_id(record_id))
        except ProofError as exc:
            raise HTTPException(502, str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/api/proposals")
    def proposals():
        return [p.model_dump(mode="json") for p in rt.proposals.all()]

    @app.post("/api/proposals/{proposal_id}/resolve")
    def resolve(proposal_id: str, req: ResolveRequest):
        try:
            return rt.updates.resolve(proposal_id, req.approve, req.approver, req.note).model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/stream")
    def stream():
        if rt.source is None:
            raise HTTPException(503, rt.source_error or "no source")
        return StreamingResponse(_mjpeg(rt), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        rt.hub.sockets.add(socket)
        await socket.send_json({"type": "state", "state": rt.state()})
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            rt.hub.sockets.discard(socket)

    return app


def _mjpeg(rt: Runtime, fps: float = 10.0):
    while rt.source is not None:
        try:
            frame = rt.source.grab()
        except ValueError:
            break
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + rt.preview.jpeg(frame) + b"\r\n"
        time.sleep(1.0 / fps)

