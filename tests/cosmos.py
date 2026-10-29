import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "cosmos"))

from clips import ClipPrep, Job, Prompts, Settings, SpecWriter  # noqa: E402
from launcher import Cosmos  # noqa: E402
from ledger import Harvest, Ledger  # noqa: E402
from run import Batch, parse  # noqa: E402

PROMPTS = Path(__file__).resolve().parent.parent / "scripts" / "cosmos" / "prompts.json"


class FakePrep:
    """Stands in for ffmpeg: copies the clip and reports a fixed frame count."""

    def __init__(self, work: Path, frames: int = 93):
        self.out_dir = work / "prepared"
        self.count = frames

    def prepare(self, src: Path) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        dst = self.out_dir / f"{src.stem}.mp4"
        shutil.copy(src, dst)
        return dst

    def frames(self, path: Path) -> int:
        return self.count


class FakeCosmos(Cosmos):
    """Writes Cosmos-shaped outputs (json at start, mp4 then txt at end) for chosen samples."""

    def __init__(self, finish: set[str] | None = None, start_only: set[str] = frozenset(),
                 interrupt: bool = False):
        super().__init__(Path("/nonexistent"), distilled=True)
        self.finish, self.start_only, self.interrupt = finish, start_only, interrupt
        self.batches: list[list[str]] = []

    def run(self, specs, out_dir, log):
        out_dir.mkdir(parents=True, exist_ok=True)
        names = [json.loads(Path(s).read_text())["name"] for s in specs]
        self.batches.append(names)
        for name in names:
            if self.finish is None or name in self.finish or name in self.start_only:
                (out_dir / f"{name}.json").write_text("{}")
            if self.finish is None or name in self.finish:
                (out_dir / f"{name}.mp4").write_bytes(b"video")
                (out_dir / f"{name}.txt").write_text("prompt")
        self.interrupted = self.interrupt
        return 0

    def commit(self):
        return "test-commit"


@pytest.fixture
def repo(tmp_path):
    clean = tmp_path / "clips" / "clean"
    clean.mkdir(parents=True)
    for stem in ("deck15", "trench34"):
        (clean / f"{stem}.mp4").write_bytes(b"clean")
    (clean / "deck15.txt").write_text("Two pine deck boards on a bench.")
    return tmp_path


def args(repo: Path, *extra: str):
    clips = repo / "clips"
    return parse(["--cloud", "nebius", "--instance", "gpu-h100-sxm 1gpu-16vcpu-200gb", "--distilled",
                  "--input", str(clips / "clean"), "--output", str(clips), "--work", str(clips / ".work"),
                  "--prompts", str(PROMPTS), "--cosmos", str(repo / "cosmos"), *extra])


def batch(repo, cosmos, *extra, frames=93):
    a = args(repo, *extra)
    b = Batch(a, cosmos=cosmos, prep=FakePrep(a.work, frames))
    b._check_cosmos = lambda: None
    return b


def test_job_names_and_prompts_use_clip_captions(repo):
    prompts = Prompts(PROMPTS, repo / "clips" / "clean")
    assert Job("deck15", "rain").name == "rain.deck15"
    assert prompts.for_job(Job("deck15", "rain")).startswith("Two pine deck boards on a bench. Heavy rain")
    assert prompts.for_job(Job("trench34", "mud")).startswith(prompts.scene)


def test_distilled_spec_uses_four_steps_and_edge_control(tmp_path):
    writer = SpecWriter(tmp_path, Prompts(PROMPTS, tmp_path), Settings(distilled=True))
    spec = json.loads(writer.write(Job("deck15", "rain"), tmp_path / "deck15.mp4").read_text())
    assert spec["num_steps"] == 4 and spec["edge"]["control_weight"] == 1.0
    assert "num_steps" not in SpecWriter(tmp_path, Prompts(PROMPTS, tmp_path), Settings()).spec(
        Job("deck15", "rain"), tmp_path / "deck15.mp4")


def test_distilled_command_sets_model_and_experimental_flag():
    cosmos = Cosmos(Path("/opt/cosmos"), distilled=True)
    assert cosmos.command([Path("a.json")], Path("out"))[-1] == "--model=edge/distilled"
    assert cosmos.env()["COSMOS_EXPERIMENTAL_CHECKPOINTS"] == "1"
    multi = Cosmos(Path("/opt/cosmos"), gpus=2).command([Path("a.json")], Path("out"))
    assert multi[0].endswith("torchrun") and "--nproc_per_node=2" in multi


def test_full_run_moves_variants_home_and_records_where(repo):
    b = batch(repo, FakeCosmos())
    assert b.run() == 0
    clips = repo / "clips"
    for condition in ("rain", "mud", "dusk_glare"):
        assert (clips / condition / "deck15.mp4").read_bytes() == b"video"
    info = (clips / "RUN_INFO.md").read_text()
    assert "| deck15 | rain | done | 93 |" in info and "nebius" in info and "test-commit" in info


def test_rerun_after_preemption_only_generates_unfinished_variants(repo):
    first = FakeCosmos(finish={"rain.deck15"}, start_only={"mud.deck15"}, interrupt=True)
    assert batch(repo, first).run() == 1
    state = Ledger(repo / "clips" / ".work" / "state.json")
    assert state.jobs["mud.deck15"]["attempts"] == 0  # preempted, not failed
    second = FakeCosmos()
    assert batch(repo, second).run() == 0
    assert "rain.deck15" not in second.batches[0]
    assert len(second.batches[0]) == 5


def test_outputs_finished_before_a_kill_are_harvested_without_rerunning(repo):
    raw = repo / "clips" / ".work" / "raw"
    raw.mkdir(parents=True)
    for ext, body in ((".json", "{}"), (".mp4", "video"), (".txt", "p")):
        (raw / f"rain.trench34{ext}").write_text(body)
    cosmos = FakeCosmos()
    batch(repo, cosmos).run()
    assert "rain.trench34" not in cosmos.batches[0]
    assert (repo / "clips" / "rain" / "trench34.mp4").exists()


def test_variant_failing_twice_is_marked_failed_and_skipped(repo):
    stuck = {"rain.deck15"}
    for _ in range(2):
        batch(repo, FakeCosmos(finish=set(), start_only=stuck), "--conditions", "rain").run()
    state = Ledger(repo / "clips" / ".work" / "state.json")
    assert state.jobs["rain.deck15"]["status"] == "failed"
    third = FakeCosmos(finish=set())
    batch(repo, third, "--conditions", "rain").run()
    assert third.batches == [["rain.trench34"]]


def test_wall_time_comes_from_cosmos_start_and_end_files(tmp_path):
    raw, dest = tmp_path / "raw", tmp_path / "out"
    raw.mkdir()
    for ext in (".json", ".mp4", ".txt"):
        (raw / f"rain.deck15{ext}").write_text("x")
    start = time.time() - 70
    os.utime(raw / "rain.deck15.json", (start, start))
    os.utime(raw / "rain.deck15.txt", (start + 64.5, start + 64.5))
    ledger = Ledger(tmp_path / "state.json")
    Harvest(raw, dest, ledger, {"cloud": "aws"}, 2).collect([Job("deck15", "rain")], count_failures=True)
    entry = ledger.jobs["rain.deck15"]
    assert entry["seconds"] == 64.5 and entry["cloud"] == "aws"


def test_dry_run_prints_command_without_running(repo, capsys):
    cosmos = FakeCosmos()
    assert batch(repo, cosmos, "--dry-run").run() == 0
    assert cosmos.batches == []
    assert "--model=edge/distilled" in capsys.readouterr().out


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_clip_prep_resamples_and_caps_frames(tmp_path):
    import subprocess

    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=30",
                    "-t", "8", "-pix_fmt", "yuv420p", str(src)], check=True)
    prep = ClipPrep(tmp_path / "work", fps=16, max_frames=93)
    out = prep.prepare(src)
    assert ClipPrep.frames(out) == 93
    assert prep.prepare(src) == out  # cached on rerun
