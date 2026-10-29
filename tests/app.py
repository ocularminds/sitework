import cv2
import pytest
from fastapi.testclient import TestClient

from sitework.app import create_app
from sitework.config import Settings
from sitework.ground.packs import Pack, PackStore
from synth import scene_with_marker


@pytest.fixture
def client(tmp_path):
    clip = tmp_path / "bench.avi"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 10, (1400, 900))
    image = scene_with_marker()
    for _ in range(10):
        writer.write(image)
    writer.release()
    for j in ("US", "SE"):
        PackStore(tmp_path / "packs").save(Pack(jurisdiction=j))
    cfg = Settings(_env_file=None, data_dir=tmp_path, sitework_source=str(clip), decionis_mode="mock",
                   nebius_api_key=None, decionis_org_id="00000000-0000-4000-8000-000000000002")
    with TestClient(create_app(cfg)) as c:
        yield c


def test_state_reports_mock_gate_and_source(client):
    st = client.get("/api/state").json()
    assert st["gate_mode"] == "mock" and st["source"] == "file:bench.avi" and st["light"]["color"] == "off"


def test_inspect_returns_a_result_pushes_it_and_stores_the_record(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state"
        r = client.post("/api/inspect", json={"scene": "decking", "condition": "clean"}).json()
        pushed = ws.receive_json()
    assert pushed["type"] == "result" and pushed["result"]["record_id"] == r["record_id"]
    assert any("NEBIUS_API_KEY" in e for e in r["errors"])
    assert r["light"]["color"] != "green"
    record = client.get(f"/api/dossiers/{r['record_id']}").json()
    assert record["gate_mode"] == "mock" and len(record["evidence"]["frame_sha256"]) == 3


def test_unbuilt_scene_and_unknown_record_are_404(client):
    assert client.post("/api/inspect", json={"scene": "welding"}).status_code == 404
    assert client.get("/api/dossiers/nope").status_code == 404


def test_pages_are_served(client):
    assert "SiteWork" in client.get("/").text and "SiteWork Light" in client.get("/light").text


def test_mock_records_cannot_be_verified_and_proposals_list(client):
    r = client.post("/api/inspect", json={"scene": "decking", "condition": "clean"}).json()
    assert client.post(f"/api/dossiers/{r['record_id']}/verify").status_code == 409
    assert client.get("/api/proposals").json() == []
    assert client.post("/api/proposals/nope/resolve", json={"approve": True, "approver": "A"}).status_code == 409
    assert "Decision dossier" in client.get("/dossier").text


def test_switching_jurisdiction_regrounds_the_last_inspection(client):
    first = client.post("/api/inspect", json={"scene": "trench", "condition": "clean"}).json()
    assert first["action"] == "trench.authorize_entry" and first["jurisdiction"] == "US"
    st = client.post("/api/jurisdiction", json={"jurisdiction": "SE"}).json()
    assert st["jurisdiction"] == "SE" and st["jurisdictions"] == ["SE", "US"]
    assert st["last"]["regrounded_from"] == first["record_id"] and st["last"]["jurisdiction"] == "SE"
    assert any("SE pack" in e for e in st["last"]["errors"])
    assert client.post("/api/jurisdiction", json={"jurisdiction": "XX"}).status_code == 404


def test_a_named_person_resolves_an_escalation_once_and_the_light_turns_blue(client):
    r = client.post("/api/inspect", json={"scene": "decking", "condition": "clean"}).json()
    assert r["verdict"]["decision"] == "ESCALATE"
    url = f"/api/dossiers/{r['record_id']}/resolve"
    assert client.post(url, json={"approver": " ", "release": True}).status_code == 409
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        out = client.post(url, json={"approver": "Ada Inspector", "release": True, "note": "re-measured by hand"}).json()
        pushed = ws.receive_json()
    assert out["light"] == {"color": "blue", "label": "RELEASED BY ADA INSPECTOR"} and pushed["type"] == "resolution"
    record = client.get(f"/api/dossiers/{r['record_id']}").json()
    assert record["resolution"]["approver"] == "Ada Inspector" and record["resolution"]["escalated_decision"] == "ESCALATE"
    assert client.get("/api/state").json()["light"]["color"] == "blue"
    assert client.post(url, json={"approver": "Someone Else", "release": False}).status_code == 409
    assert client.post("/api/dossiers/nope/resolve", json={"approver": "A", "release": True}).status_code == 404
