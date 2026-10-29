from datetime import datetime, timezone

import numpy as np
import pytest

from sitework.capture import Frame, Source
from sitework.config import Settings
from sitework.dossier import DossierStore
from sitework.gate.authority import MockGate
from sitework.ground.citation import Clause
from sitework.ground.packs import Pack, PackStore
from sitework.perceive.vlm import VisionError
from sitework.scenes import DeckingInspection
from synth import deck_scene, deck_view, scene_with_marker


class StillSource(Source):
    label = "test:still"

    def __init__(self, image):
        self.image = image

    def grab(self):
        return Frame(self.image.copy(), 0)

    def sample(self, count):
        return [Frame(self.image.copy(), i) for i in range(count)]


class FakeVision:
    model = "acme/vl-test"

    def __init__(self, view=None, fail=False):
        self.view, self.fail = view, fail

    def locate(self, frame, schema):
        if self.fail:
            raise VisionError("invalid reply after retry: boards: too short")
        return self.view


def settings(tmp_path, **over) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, nebius_api_key=None, sitework_samples=3,
                    decionis_org_id="00000000-0000-4000-8000-000000000002", **over)


def approved_pack(store: PackStore) -> None:
    clause = Clause(excerpt="Spacing between boards should be 1/8” to 1/4”.", url="https://www.timbertech.com/x",
                    source_domain="www.timbertech.com", content_sha256="c" * 64,
                    retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc), mm_values=[3.17, 6.35])
    pack = Pack(jurisdiction="US", allowlist={"decking": ["timbertech.com"]})
    pack.approve("decking", clause, "Side gap 1/8 to 1/4 in", {"gap_mm": {"min": 3.17, "max": 6.35}}, "A Person")
    store.save(pack)


def inspection(tmp_path, vision, decision="ESCALATE", pack=True):
    cfg = settings(tmp_path)
    packs = PackStore(tmp_path / "packs")
    if pack:
        approved_pack(packs)
    gate = MockGate(cfg, decision)
    return DeckingInspection(cfg, gate, DossierStore(tmp_path / "dossiers"), packs, vision=vision)


def test_clean_flow_measures_cites_and_stores_a_record(tmp_path):
    image, view = deck_scene(2.0, 5.0)
    flow = inspection(tmp_path, FakeVision(view), decision="ALLOW")
    r = flow.run(StillSource(image), "clean", "US")
    assert r.errors == []
    assert [m.kind for m in r.measurements] == ["angle_deg", "gap_mm", "gap_mm"]
    assert r.measurements[0].value == pytest.approx(2.0, abs=0.1)
    assert r.citations[0].requirement == "Side gap 1/8 to 1/4 in"
    assert {c["kind"] for c in r.checks} == {"gap_mm"}
    assert r.light.color == "green" and r.gate_mode == "mock"
    assert r.overlay and len(r.overlay.marker) == 4 and len(r.overlay.segments) == 4
    record = flow.store.get(r.record_id)
    assert record.evidence.models == {"vlm": "acme/vl-test"} and len(record.evidence.frame_sha256) == 3


def test_lines_with_no_image_edge_under_them_are_errors_and_never_green(tmp_path):
    flow = inspection(tmp_path, FakeVision(deck_view(2.0, 5.0)), decision="ALLOW")
    r = flow.run(StillSource(scene_with_marker()), "clean", "US")  # the boards are not in the picture
    assert sum("no clear image edges" in e for e in r.errors) == 3 and r.measurements == []
    sent = flow.store.get(r.record_id).exchange.request["context"]["sitework"]
    assert sent["summary"]["error_count"] == len(r.errors)  # the real gate's interlock and policy act on this
    assert "snapped to image edges" in flow.measured_by


def test_missing_marker_and_missing_citation_reach_the_gate_as_errors(tmp_path):
    flow = inspection(tmp_path, FakeVision(deck_view(0.0, 5.0)), pack=False)
    r = flow.run(StillSource(np.full((480, 640, 3), 255, np.uint8)), "rain", "US")
    assert r.measurements == []
    assert sum(e.startswith("fiducial[") for e in r.errors) == 3
    assert any(e.startswith("grounding:") for e in r.errors)
    sent = flow.store.get(r.record_id).exchange.request["context"]["sitework"]
    assert sent["summary"]["error_count"] == len(r.errors) and sent["citations"] == []


def test_vision_failure_and_missing_key_are_recorded_not_raised(tmp_path):
    failing = inspection(tmp_path, FakeVision(fail=True)).run(StillSource(scene_with_marker()), "clean", "US")
    assert sum(e.startswith("vision[") for e in failing.errors) == 3 and failing.measurements == []
    keyless = inspection(tmp_path, vision=None).run(StillSource(scene_with_marker()), "clean", "US")
    assert any("NEBIUS_API_KEY" in e for e in keyless.errors)
    assert keyless.light.color == "amber"  # the mock returned ESCALATE; never green here


def test_no_source_still_proposes_with_the_capture_error(tmp_path):
    r = inspection(tmp_path, FakeVision(deck_view(0.0, 5.0))).run(None, "clean", "US")
    assert r.errors[0] == "capture: no video source is open" and r.overlay is None
