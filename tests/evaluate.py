import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pytest

from sitework.config import Settings
from sitework.evaluate import Label, LabelFile, MarkdownReport, Results, Run, Scored, Scorer
from sitework.light import LightState
from sitework.scenes import InspectionResult
from sitework.schema import Measurement, Verdict
from synth import scene_with_marker

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eval_script", ROOT / "scripts" / "eval.py")
evalscript = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evalscript)

HEADER = "clip,scene,condition,jurisdiction,gap_min_mm,gap_max_mm,angle_deg,slope_deg,depth_mm,seated,expected,notes\n"


def result(measurements, decision="BLOCK", latency=120.0, dossier="d-1", scene="decking") -> InspectionResult:
    verdict = Verdict(decision=decision, reason="r", dossier_id=dossier, latency_ms=latency) if decision else None
    return InspectionResult(record_id=dossier or "no-decision-x", created_at=datetime.now(timezone.utc), scene=scene,
                            action="inspection.release_hold", condition="clean", jurisdiction="US", gate_mode="live",
                            measurements=measurements, citations=[], checks=[], errors=[], verdict=verdict,
                            failure=None, light=LightState.idle(), overlay=None)


def m(kind, value, method="t", confidence=0.9):
    return Measurement(kind=kind, value=value, confidence=confidence, method=method)


def test_label_file_parses_blanks_booleans_and_rejects_missing_columns(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(HEADER + "data/clips/clean/deck.mp4,decking,clean,US,5,15.4,3,,,,BLOCK,known 3°\n"
                    "data/clips/clean/joint.mp4,plumbing,rain,SE,,,1,,,true,ALLOW,\n\n")
    a, b = LabelFile(path).read()
    assert (a.gap_min_mm, a.slope_deg, a.seated, a.expected) == (5.0, None, None, "BLOCK")
    assert (b.jurisdiction, b.seated, b.condition) == ("SE", True, "rain")
    path.write_text("clip,scene\nx,decking\n")
    with pytest.raises(ValueError, match="missing columns"):
        LabelFile(path).read()


def test_scorer_maps_measurements_to_truth_and_flags_false_allows():
    label = Label(clip="c", scene="decking", condition="clean", gap_min_mm=5.0, gap_max_mm=15.0, angle_deg=3.0,
                  expected="BLOCK")
    s = Scorer().score(label, result([m("angle_deg", 3.4), m("gap_mm", 5.3, "narrowest point of any joint"),
                                      m("gap_mm", 14.0, "widest point of any joint")], decision="ALLOW"))
    assert s.abs_error == {"angle_deg": 0.4, "gap_min_mm": 0.3, "gap_max_mm": 1.0}
    assert s.false_allow and not s.correct and not s.escalated and s.min_confidence == 0.9


def test_review_required_counts_as_a_correct_escalation_and_seats_are_scored():
    label = Label(clip="c", scene="plumbing", condition="mud", seated=True, expected="ESCALATE")
    s = Scorer().score(label, result([m("seat_audio", True)], decision="REVIEW_REQUIRED", scene="plumbing"))
    assert s.correct and s.escalated and s.seat_correct is True
    none = Scorer().score(label, result([], decision=None, dossier=""))
    assert none.decision == "NO DECISION" and not none.correct and none.latency_ms is None


def row(condition, expected, decision, conf=0.8, latency=100.0, dossier="d", verified=None):
    return Scored(clip="c", scene="decking", condition=condition, jurisdiction="US", expected=expected,
                  decision=decision, correct=decision == expected, false_allow=decision == "ALLOW" and expected != "ALLOW",
                  escalated=decision == "ESCALATE", min_confidence=conf, latency_ms=latency, record_id=dossier,
                  dossier_id=dossier, verified=verified)


def test_run_statistics_per_condition_p95_floor_and_dossiers():
    rows = [row("clean", "ALLOW", "ALLOW", verified=True), row("clean", "BLOCK", "BLOCK", verified=True),
            row("rain", "BLOCK", "ALLOW", conf=0.861, latency=900.0, verified=False),
            row("rain", "ALLOW", "ESCALATE", dossier="mock-1"),
            *[row("rain", "BLOCK", "BLOCK", latency=float(i)) for i in range(16)]]
    run = Run(label="run 1", gate_mode="SHADOW", decionis_mode="live", rows=rows)
    clean, rain = run.by_condition()
    assert (clean.n, clean.correct_rate, clean.false_allow_rate) == (2, 1.0, 0.0) and clean.suggested_floor is None
    assert (rain.n, rain.false_allows, rain.suggested_floor) == (18, 1, 0.87)
    assert rain.escalate_rate == round(1 / 18, 3)
    assert run.p95_latency_ms() == 100.0  # nearest rank: 19th of 20 sorted latencies
    assert run.dossiers() == (19, 2, 3)


def test_markdown_lists_runs_newest_first_and_warns_about_mock():
    first = Run(label="run 1", gate_mode="SHADOW", decionis_mode="live", floors={"rain": 0.85},
                rows=[row("rain", "BLOCK", "ALLOW", conf=0.861)])
    second = Run(label="run 2: rain floor 0.87", gate_mode="SHADOW", decionis_mode="mock",
                 rows=[row("rain", "BLOCK", "ESCALATE")])
    md = MarkdownReport().render(Results(runs=[first, second]))
    assert md.index("## run 2") < md.index("## run 1")
    assert "MOCK GATE" in md.split("## run 1")[0] and "MOCK GATE" not in md.split("## run 1")[1]
    for metric in ("Measurement error (gap mm / angle °)", "Correct verdict rate", "False-ALLOW rate", "ESCALATE rate"):
        assert metric in md
    assert "⚠ false ALLOW" in md and "raising the floor to 0.87" in md and "Cosmos rain (n=1)" in md


def test_policy_floors_are_read_from_the_policy_file():
    assert evalscript.Floors.read(ROOT / "policies" / "sitework.json") == {
        "clean": 0.7, "outdoor": 0.75, "rain": 0.85, "mud": 0.85, "dusk_glare": 0.85}


def test_end_to_end_with_mock_gate_into_a_test_directory(tmp_path, monkeypatch, capsys):
    clip = tmp_path / "deck.avi"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 10, (1400, 900))
    for _ in range(6):
        writer.write(scene_with_marker())
    writer.release()
    labels = tmp_path / "labels.csv"
    labels.write_text(HEADER + f"{clip},decking,clean,US,5,5,0,,,,ALLOW,\n")
    cfg = Settings(_env_file=None, data_dir=tmp_path, decionis_mode="mock", nebius_api_key=None,
                   decionis_org_id="00000000-0000-4000-8000-000000000002")
    monkeypatch.setattr(evalscript, "get_settings", lambda: cfg)
    assert evalscript.main(["--labels", str(labels), "--run-label", "t"]) == 2  # mock never writes into eval/
    out = tmp_path / "out"
    assert evalscript.main(["--labels", str(labels), "--run-label", "t", "--output", str(out)]) == 0
    stored = Results.load(out / "results.json").runs[0]
    assert stored.rows[0].decision == "ESCALATE" and stored.gate_mode == "SHADOW" and stored.decionis_mode == "mock"
    assert "MOCK GATE" in (out / "results.md").read_text()
    labels.write_text(HEADER + "missing/clip.mp4,decking,clean,US,,,,,,,ALLOW,\n")
    assert evalscript.main(["--labels", str(labels), "--run-label", "t", "--output", str(out)]) == 2
    assert "missing clips" in capsys.readouterr().out
