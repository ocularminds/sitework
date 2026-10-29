"""FastAPI app: live feed, inspection trigger, verdict push over WebSocket, dossier lookup.

Run with `uvicorn sitework.app:create_app --factory` (or `make demo`).
"""

import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from sitework.capture import Source, open_source
from sitework.config import ROOT, Settings, get_settings
from sitework.dossier import DossierStore
from sitework.gate.authority import make_gate
from sitework.ground.packs import PackStore
from sitework.ground.watch import PolicyUpdate, ProposalStore
from sitework.light import LightState
from sitework.proof import ProofError, Proofs
from sitework.scenes import DeckingInspection, InspectionResult
from sitework.schema import Action, Condition

STATIC = ROOT / "static"


class InspectRequest(BaseModel):
    scene: str = "decking"
    condition: Condition = "clean"
    action: Action = "inspection.release_hold"


class SourceRequest(BaseModel):
    spec: str


class ResolveRequest(BaseModel):
    approve: bool
    approver: str
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
        self.scenes = {"decking": DeckingInspection(settings, self.gate, self.store, self.packs)}
        self.proofs = Proofs(settings)
        self.proposals = ProposalStore(settings.data_dir / "proposals")
        self.updates = PolicyUpdate(self.gate, self.proposals)
        self.jurisdiction = settings.sitework_jurisdiction
        self.source: Source | None = None
        self.source_error = ""
        self.last: InspectionResult | None = None
        self.hub = Hub()
        self._busy = threading.Lock()
        self.open(settings.sitework_source)

    def open(self, spec: str) -> None:
        if self.source is not None:
            self.source.close()
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
            return self.last
        finally:
            self._busy.release()

    @staticmethod
    def dossier_id(record_id: str) -> str:
        """Records named after a Decionis dossier can be verified; mock and no-decision records cannot."""
        if record_id.startswith(("mock-", "no-decision-")):
            raise HTTPException(409, "this record has no Decionis dossier to verify")
        return record_id

    def state(self) -> dict:
        return {
            "source": self.source.label if self.source else None,
            "source_error": self.source_error,
            "gate_mode": self.gate.mode,
            "gateway": self.settings.decionis_gateway_url,
            "gate_route": self.settings.decionis_gate_route,
            "jurisdiction": self.jurisdiction,
            "scenes": list(self.scenes),
            "vlm_model": self.settings.nebius_vlm_model,
            "light": (self.last.light if self.last else LightState.idle()).model_dump(),
            "last": self.last.model_dump(mode="json") if self.last else None,
        }


def create_app(settings: Settings | None = None) -> FastAPI:
    rt = Runtime(settings or get_settings())
    app = FastAPI(title="SiteWork")
    app.state.runtime = rt

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/light")
    def light():
        return FileResponse(STATIC / "light.html")

    @app.get("/api/state")
    def state():
        return rt.state()

    @app.post("/api/source")
    def source(req: SourceRequest):
        rt.open(req.spec)
        return rt.state()

    @app.post("/api/inspect")
    async def inspect(req: InspectRequest):
        result = await run_in_threadpool(rt.inspect, req)
        payload = result.model_dump(mode="json")
        await rt.hub.send({"type": "result", "result": payload, "light": payload["light"]})
        return payload

    @app.get("/api/dossiers/{record_id}")
    def dossier(record_id: str):
        record = rt.store.get(record_id)
        if record is None:
            raise HTTPException(404, "no such record")
        return record.model_dump(mode="json")

    @app.get("/dossier")
    def dossier_page():
        return FileResponse(STATIC / "dossier.html")

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
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame.jpeg + b"\r\n"
        time.sleep(1.0 / fps)

