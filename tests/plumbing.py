import json
from datetime import datetime, timezone

import pytest

from sitework.capture import FileAudio, MicAudio, open_audio
from sitework.config import Settings
from sitework.dossier import DossierStore
from sitework.gate.authority import MockGate
from sitework.ground.citation import Clause
from sitework.ground.packs import Pack, PackStore
from sitework.measure.align import AlignmentMeasurer
from sitework.measure.fiducial import Fiducial
from sitework.perceive.audio import AudioError, AudioModel, SeatDsp, SeatReply
from sitework.scenes import PlumbingInspection
from scenes import FakeVision, StillSource
from synth import joint_audio, plumbing_view, scene_with_marker
from vlm import FakeClient


@pytest.mark.parametrize("kind,seated", [("click", True), ("noise", False), ("thud", False)])
def test_dsp_hears_a_seat_click_but_not_noise_or_a_thud(kind, seated):
    r = SeatDsp().analyse(joint_audio(kind))
    assert r.seated is seated
    if kind == "click":
        assert r.onset_s == pytest.approx(1.5, abs=0.05) and r.centroid_hz > 3000


def test_dsp_refuses_silence():
    import numpy as np
    from sitework.capture import AudioClip
    with pytest.raises(ValueError, match="silent"):
        SeatDsp().analyse(AudioClip(np.zeros(16000, np.float32), 16000, "silence"))


def test_audio_model_sends_wav_and_retries_once():
    client = FakeClient(["no", json.dumps({"seated": True, "confidence": 0.8})])
    reply = AudioModel(client, "acme/omni").listen(joint_audio("click"))
    assert reply == SeatReply(seated=True, confidence=0.8) and len(client.calls) == 2
    part = client.calls[0]["messages"][0]["content"][0]
    assert part["type"] == "input_audio" and part["input_audio"]["format"] == "wav"
    with pytest.raises(AudioError, match="nebius_audio_model"):
        AudioModel(client, "")


def test_alignment_angle_on_the_marker_plane():
    scale = Fiducial(40.0).detect(scene_with_marker())
    for angle in (0.0, 4.0, 12.0):
        assert AlignmentMeasurer().sample(plumbing_view(angle), scale, 0).angle_deg == pytest.approx(angle, abs=0.2)


class FakeAudio:
    label = "test:audio"

    def __init__(self, clip):
        self.clip = clip

    def record(self, seconds):
        if self.clip is None:
            raise ValueError("no audio track in clip.mp4")
        return self.clip


class FakeEar:
    model = "acme/omni-test"

    def __init__(self, seated: bool):
        self.seated = seated

    def listen(self, clip):
        return SeatReply(seated=self.seated, confidence=0.9)


def pack_store(tmp_path, threshold) -> PackStore:
    store = PackStore(tmp_path / "packs")
    pack = Pack(jurisdiction="US", allowlist={"plumbing": ["sharkbite.com"]})
    clause = Clause(excerpt="Push the fitting to your insertion depth mark.", url="https://www.sharkbite.com/x",
                    source_domain="www.sharkbite.com", content_sha256="e" * 64,
                    retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc), mm_values=[])
    pack.approve("plumbing", clause, "Joint fully inserted and square", threshold, "A Person")
    store.save(pack)
    return store


def flow(tmp_path, clip, ear, threshold=None):
    cfg = Settings(_env_file=None, data_dir=tmp_path, decionis_org_id="00000000-0000-4000-8000-000000000002",
                   nebius_api_key=None)
    threshold = threshold if threshold is not None else {"seat_audio": {"min": 1}, "angle_deg": {"max": 2.0}}
    return PlumbingInspection(cfg, MockGate(cfg, "ALLOW"), DossierStore(tmp_path / "dossiers"),
                              pack_store(tmp_path, threshold), vision=FakeVision(plumbing_view(1.0)),
                              audio=FakeAudio(clip), audio_model=ear)


def test_seated_by_ear_and_aligned_by_eye_gives_both_checks(tmp_path):
    r = flow(tmp_path, joint_audio("click"), FakeEar(True)).run(StillSource(scene_with_marker()), "clean", "US")
    assert r.errors == []
    assert {(c["kind"], c["within"]) for c in r.checks} == {("seat_audio", True), ("angle_deg", True)}
    record = flow(tmp_path, joint_audio("click"), FakeEar(True)).store.get(r.record_id)
    assert record.evidence.audio_sha256 and record.evidence.models["audio"] == "acme/omni-test"


def test_agreeing_not_seated_is_a_failed_check_not_an_error(tmp_path):
    r = flow(tmp_path, joint_audio("thud"), FakeEar(False)).run(StillSource(scene_with_marker()), "clean", "US")
    assert r.errors == [] and ("seat_audio", False) in {(c["kind"], c["within"]) for c in r.checks}


def test_model_and_dsp_disagreeing_is_an_error_so_the_policy_escalates(tmp_path):
    r = flow(tmp_path, joint_audio("noise"), FakeEar(True)).run(StillSource(scene_with_marker()), "clean", "US")
    assert any(e.startswith("audio: model says seated") for e in r.errors)
    assert all(m.kind != "seat_audio" for m in r.measurements)


def test_missing_audio_and_unbounded_requirements_are_errors(tmp_path):
    r = flow(tmp_path, None, FakeEar(True), threshold={"angle_deg": {"max": 2.0}}).run(
        StillSource(scene_with_marker()), "clean", "US")
    assert "audio: no audio track in clip.mp4" in r.errors
    assert "grounding: no approved US requirement sets a threshold for seat_audio" in r.errors


def test_open_audio_follows_the_video_source():
    assert isinstance(open_audio("", "0"), MicAudio) and isinstance(open_audio("", "/clips/joint.mp4"), FileAudio)
    assert open_audio("mic:2").device == 2 and open_audio("/x.wav").path.name == "x.wav"


def test_file_audio_reads_a_clip_track_with_ffmpeg(tmp_path):
    clip = joint_audio("click")
    path = tmp_path / "joint.wav"
    path.write_bytes(clip.wav)
    got = FileAudio(path).record(3.0)
    assert got.rate == 16000 and abs(got.seconds - 3.0) < 0.01
    with pytest.raises(ValueError, match="no audio track"):
        FileAudio(tmp_path / "missing.mp4").record(3.0)
