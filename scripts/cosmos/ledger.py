"""Batch state: which variants are done, moving outputs home, and the RUN_INFO record."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from clips import Job


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ledger:
    """Per-job status in `state.json`, written atomically so a kill never corrupts it."""

    def __init__(self, path: Path):
        self.path = path
        self.jobs: dict[str, dict] = json.loads(path.read_text()) if path.exists() else {}

    def entry(self, job: Job) -> dict:
        return self.jobs.setdefault(job.name, {
            "clip": job.clip, "condition": job.condition, "status": "pending", "attempts": 0,
        })

    def pending(self, jobs: list[Job], max_attempts: int) -> list[Job]:
        return [j for j in jobs
                if self.entry(j)["status"] != "done" and self.entry(j)["attempts"] < max_attempts]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.partial")
        tmp.write_text(json.dumps(self.jobs, indent=2, sort_keys=True))
        os.replace(tmp, self.path)


class Harvest:
    """Copies finished Cosmos outputs to `<dest>/<condition>/<clip>.mp4` and updates the ledger.

    Cosmos writes `<name>.json` when a sample starts and `<name>.txt` only after the video
    is saved, so the `.txt` marks a complete output and the two mtimes give its wall time.
    """

    def __init__(self, raw: Path, dest: Path, ledger: Ledger, where: dict, max_attempts: int):
        self.raw = raw
        self.dest = dest
        self.ledger = ledger
        self.where = where
        self.max_attempts = max_attempts

    def collect(self, jobs: list[Job], count_failures: bool) -> None:
        for job in jobs:
            entry = self.ledger.entry(job)
            if entry["status"] == "done":
                continue
            video, started, finished = (self.raw / f"{job.name}{ext}" for ext in (".mp4", ".json", ".txt"))
            if video.exists() and finished.exists():
                self._keep(job, video)
                seconds = finished.stat().st_mtime - started.stat().st_mtime if started.exists() else None
                entry.update(status="done", seconds=None if seconds is None else round(seconds, 1),
                             finished_at=now(), **self.where)
            elif started.exists() and count_failures:
                entry["attempts"] += 1
                if entry["attempts"] >= self.max_attempts:
                    entry["status"] = "failed"
        self.ledger.save()

    def clear_partial(self, jobs: list[Job]) -> None:
        """Drop leftovers of unfinished samples so a rerun starts (and is timed) cleanly."""
        for job in jobs:
            for ext in (".mp4", ".json", ".txt"):
                (self.raw / f"{job.name}{ext}").unlink(missing_ok=True)

    def _keep(self, job: Job, video: Path) -> None:
        target = self.dest / job.condition / f"{job.clip}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{job.clip}.partial.mp4")
        shutil.copy2(video, tmp)
        os.replace(tmp, target)


class RunInfo:
    """Renders `RUN_INFO.md` from the ledger: where each variant ran and how long it took."""

    def __init__(self, path: Path, settings: dict):
        self.path = path
        self.settings = settings

    def render(self, ledger: Ledger, jobs: list[Job]) -> str:
        lines = [
            "# Cosmos Transfer 2.5 run",
            "",
            f"Written by `scripts/cosmos/run.py` from its ledger. Updated {now()}.",
            "",
            "| Setting | Value |",
            "|---|---|",
            *[f"| {k} | {v} |" for k, v in self.settings.items()],
            "",
            "| Clip | Condition | Status | Frames | Seconds | Cloud | Instance | GPU | Finished (UTC) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for job in jobs:
            e = ledger.entry(job)
            cells = [job.clip, job.condition, e["status"], e.get("frames", ""), e.get("seconds", ""),
                     e.get("cloud", ""), e.get("instance", ""), e.get("gpu", ""), e.get("finished_at", "")]
            lines.append("| " + " | ".join("" if c is None else str(c) for c in cells) + " |")
        return "\n".join(lines) + "\n"

    def write(self, ledger: Ledger, jobs: list[Job]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.render(ledger, jobs))
