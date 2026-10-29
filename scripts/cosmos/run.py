"""Resumable Cosmos Transfer 2.5 batch: clean clips -> rain / mud / dusk_glare variants.

Stdlib only, so it runs with the GPU VM's system Python beside a Cosmos checkout.
Re-run the same command after a preemption: finished variants are kept and only
unfinished ones are generated again. See README.md in this folder.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from clips import VIDEO_EXTS, ClipPrep, Job, Prompts, Settings, SpecWriter
from launcher import Cosmos, gpu_summary
from ledger import Harvest, Ledger, RunInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DISTILLED_FRAMES = 93  # the distilled model is trained for exactly one 93-frame chunk


class Batch:
    """Plans pending jobs, prepares inputs, runs Cosmos once and harvests the results."""

    def __init__(self, args: argparse.Namespace, cosmos: Cosmos | None = None,
                 prep: ClipPrep | None = None):
        self.args = args
        self.settings = Settings(guidance=args.guidance, seed=args.seed, edge_weight=args.edge_weight,
                                 edge_threshold=args.edge_threshold, distilled=args.distilled)
        self.max_frames = args.max_frames or (DISTILLED_FRAMES if args.distilled else None)
        self.prep = prep or ClipPrep(args.work, args.fps, self.max_frames)
        self.cosmos = cosmos or Cosmos(args.cosmos, args.gpus, args.distilled)
        self.prompts = Prompts(args.prompts, args.input)
        self.raw = args.work / "raw"
        self.ledger = Ledger(args.work / "state.json")
        where = {"cloud": args.cloud, "instance": args.instance, "gpu": gpu_summary()}
        self.harvest = Harvest(self.raw, args.output, self.ledger, where, args.max_attempts)
        self.specs = SpecWriter(args.work / "specs", self.prompts, self.settings)

    @property
    def conditions(self) -> list[str]:
        chosen = self.args.conditions or list(self.prompts.conditions)
        unknown = sorted(set(chosen) - set(self.prompts.conditions))
        if unknown:
            raise SystemExit(f"unknown condition(s) {unknown}; add them to {self.args.prompts}")
        return chosen

    def clips(self) -> dict[str, Path]:
        files = sorted(p for p in self.args.input.iterdir() if p.suffix.lower() in VIDEO_EXTS)
        if not files:
            raise SystemExit(f"no clips ({', '.join(sorted(VIDEO_EXTS))}) in {self.args.input}")
        stems = [p.stem for p in files]
        if len(set(stems)) != len(stems):
            raise SystemExit(f"clip names must be unique ignoring extension: {stems}")
        return {p.stem: p for p in files}

    def run(self) -> int:
        clips = self.clips()
        jobs = [Job(stem, c) for stem in clips for c in self.conditions]
        self.harvest.collect(jobs, count_failures=False)  # outputs finished before a preemption
        pending = self.ledger.pending(jobs, self.args.max_attempts)
        if pending:
            specs = self._prepare(pending, clips)
            if self.args.dry_run:
                print(" ".join(self.cosmos.command(specs, self.raw)))
                return 0
            self._check_cosmos()
            self.harvest.clear_partial(pending)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            code = self.cosmos.run(specs, self.raw, self.args.work / "logs" / f"{stamp}.log")
            print(f"cosmos exited with code {code}")
            self.harvest.collect(pending, count_failures=not self.cosmos.interrupted)
        RunInfo(self.args.output / "RUN_INFO.md", self._settings()).write(self.ledger, jobs)
        return self._summary(jobs)

    def _prepare(self, pending: list[Job], clips: dict[str, Path]) -> list[Path]:
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            raise SystemExit("ffmpeg/ffprobe not found; run scripts/cosmos/setup.sh")
        prepared: dict[str, tuple[Path, int]] = {}
        for stem in sorted({j.clip for j in pending}):
            video = self.prep.prepare(clips[stem])
            prepared[stem] = (video, self.prep.frames(video))
            if self.settings.distilled and prepared[stem][1] < DISTILLED_FRAMES:
                print(f"warning: {stem} has {prepared[stem][1]} frames; the distilled model "
                      f"expects {DISTILLED_FRAMES}. Record at least {DISTILLED_FRAMES / self.args.fps:.1f} s.")
        specs = []
        for job in pending:
            video, frames = prepared[job.clip]
            self.ledger.entry(job)["frames"] = frames
            specs.append(self.specs.write(job, video))
        self.ledger.save()
        return specs

    def _check_cosmos(self) -> None:
        repo = self.args.cosmos
        if not (repo / "examples" / "inference.py").exists() or not (repo / ".venv").exists():
            raise SystemExit(f"no Cosmos checkout with .venv at {repo}; run scripts/cosmos/setup.sh")

    def _settings(self) -> dict[str, object]:
        s = self.settings
        return {
            "Model": f"Cosmos-Transfer2.5-2B `{s.model}`",
            "Cosmos commit": f"`{self.cosmos.commit()}`",
            "Control": f"edge, weight {s.edge_weight}, threshold {s.edge_threshold}",
            "Steps": s.num_steps or "Cosmos default",
            "Guidance / seed": f"{s.guidance} / {s.seed}",
            "Input": f"{self.args.fps} fps, max {self.max_frames or 'all'} frames",
            "Prompts": f"`{self.args.prompts.name}`",
        }

    def _summary(self, jobs: list[Job]) -> int:
        status = [self.ledger.entry(j)["status"] for j in jobs]
        counts = {s: status.count(s) for s in ("done", "pending", "failed")}
        print(f"variants: {counts['done']} done, {counts['pending']} pending, {counts['failed']} failed "
              f"(of {len(jobs)})")
        if self.cosmos.interrupted:
            print("interrupted: rerun the same command to resume")
        if counts["failed"]:
            print(f"failed jobs exhausted --max-attempts; see {self.args.work / 'logs'}")
        return 0 if counts["done"] == len(jobs) else 1


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cloud", required=True, choices=["nebius", "aws", "other"],
                   help="where this run executes; recorded in RUN_INFO.md")
    p.add_argument("--instance", required=True,
                   help='VM type as provisioned, e.g. "gpu-h100-sxm 1gpu-16vcpu-200gb" or "p5.4xlarge"')
    p.add_argument("--distilled", action="store_true",
                   help="4-step distilled edge model; clips are cut to 93 frames")
    p.add_argument("--conditions", nargs="+", help="subset of conditions in prompts.json")
    p.add_argument("--input", type=Path, default=REPO / "data/clips/clean")
    p.add_argument("--output", type=Path, default=REPO / "data/clips")
    p.add_argument("--work", type=Path, default=REPO / "data/clips/.work")
    p.add_argument("--prompts", type=Path, default=HERE / "prompts.json")
    p.add_argument("--cosmos", type=Path,
                   default=Path(os.environ.get("COSMOS_DIR", Path.home() / "cosmos-transfer2.5")))
    p.add_argument("--gpus", type=int, default=1, help="GPUs on this VM (uses torchrun when > 1)")
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--max-frames", type=int, help="frame cap per clip (default 93 with --distilled)")
    p.add_argument("--guidance", type=int, default=3, choices=range(8), metavar="0-7")
    p.add_argument("--seed", type=int, default=2025)
    p.add_argument("--edge-weight", type=float, default=1.0)
    p.add_argument("--edge-threshold", default="medium",
                   choices=["very_low", "low", "medium", "high", "very_high"])
    p.add_argument("--max-attempts", type=int, default=2,
                   help="give up on a variant after this many started-but-unfinished runs")
    p.add_argument("--dry-run", action="store_true", help="prepare clips and specs, print the command")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(Batch(parse()).run())
