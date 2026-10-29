from datetime import datetime, timezone

import pytest

from sitework.config import Settings
from sitework.dossier import DossierStore
from sitework.gate.authority import MockGate
from sitework.ground.citation import Clause
from sitework.ground.packs import Pack, PackStore
from sitework.measure.fiducial import Fiducial
from sitework.measure.trench import TrenchMeasurer
from sitework.scenes import TrenchInspection
from synth import scene_with_marker, trench_view
from scenes import FakeVision, StillSource


@pytest.fixture(scope="module")
def scale():
    return Fiducial(40.0).detect(scene_with_marker())


@pytest.mark.parametrize("slope,depth,tol", [(34.0, 60.0, 0.3), (53.13, 45.0, 0.3), (80.0, 30.0, 0.5)])
def test_slope_and_depth_on_the_upright_marker_plane(scale, slope, depth, tol):
    s = TrenchMeasurer().sample(trench_view(slope, depth), scale, 0)
    assert s.slope_deg == pytest.approx(slope, abs=tol)  # steep walls have little run, so more error
    assert s.depth_mm == pytest.approx(depth, abs=0.6)


def test_flat_wall_is_a_measurement_error(scale):
    from sitework.perceive.views import TrenchView
    from synth import to_px
    flat = TrenchView(confidence=0.9, walls=[{"top": to_px([[10, 60]])[0].tolist(), "toe": to_px([[50, 60]])[0].tolist()}])
    with pytest.raises(ValueError, match="same height"):
        TrenchMeasurer().sample(flat, scale, 0)


def clause(url: str, domain: str, excerpt: str) -> Clause:
    return Clause(excerpt=excerpt, url=url, source_domain=domain, content_sha256="d" * 64,
                  retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc), mm_values=[])


def packs(tmp_path) -> PackStore:
    store = PackStore(tmp_path / "packs")
    us = Pack(jurisdiction="US", allowlist={"trench": ["osha.gov"]})
    us.approve("trench", clause("https://www.osha.gov/b", "www.osha.gov", "Maximum allowable slope of 1½:1."),
               "Type C soil: max slope 1½:1 (34°)", {"slope_deg": {"max": 34.0}}, "A Person")
    se = Pack(jurisdiction="SE", allowlist={"trench": ["av.se"]})
    se.approve("trench", clause("https://www.av.se/ras", "www.av.se", "Oftast behövs stödkonstruktioner eller släntlutning."),
               "AFS 2023:13: support or sloping chosen by risk assessment (no fixed slope)", {}, "A Person")
    store.save(us)
    store.save(se)
    return store


def test_trench_entry_checks_slope_and_regrounds_under_another_jurisdiction(tmp_path):
    cfg = Settings(_env_file=None, data_dir=tmp_path, decionis_org_id="00000000-0000-4000-8000-000000000002",
                   nebius_api_key=None)
    flow = TrenchInspection(cfg, MockGate(cfg, "BLOCK"), DossierStore(tmp_path / "dossiers"), packs(tmp_path),
                            vision=FakeVision(trench_view(60.0, 40.0)))
    us = flow.run(StillSource(scene_with_marker()), "clean", "US")
    assert us.action == "trench.authorize_entry" and us.errors == []
    assert [c["within"] for c in us.checks] == [False]  # 60° is steeper than 34°
    se = flow.reground(flow.store.get(us.record_id), "SE")
    assert se.regrounded_from == us.record_id and se.jurisdiction == "SE"
    assert se.measurements == us.measurements and se.checks == []
    assert se.citations[0].source_domain == "www.av.se" and se.overlay is None
    request = flow.store.get(se.record_id).exchange.request["context"]
    assert request["sitework_checks_total"] == 0 and request["sitework_citation_count"] == 1


def test_reground_to_a_pack_without_requirements_records_the_grounding_error(tmp_path):
    cfg = Settings(_env_file=None, data_dir=tmp_path, decionis_org_id="00000000-0000-4000-8000-000000000002",
                   nebius_api_key=None)
    store = packs(tmp_path)
    flow = TrenchInspection(cfg, MockGate(cfg), DossierStore(tmp_path / "dossiers"), store,
                            vision=FakeVision(trench_view(30.0, 40.0)))
    us = flow.run(StillSource(scene_with_marker()), "clean", "US")
    other = flow.reground(flow.store.get(us.record_id), "DE")
    assert other.citations == [] and other.errors == ["grounding: no approved trench requirement in the DE pack"]
