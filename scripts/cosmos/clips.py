"""Inputs for a Cosmos batch: jobs, prompts, normalised clips and spec files."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


@dataclass(frozen=True)
class Job:
    """One clean clip rendered under one condition."""

    clip: str
    condition: str

    @property
    def name(self) -> str:
        """Cosmos sample name; outputs land at `<out>/<name>.mp4`."""
        return f"{self.condition}.{self.clip}"


class Prompts:
    """A scene caption (per clip if `<stem>.txt` sits beside it) plus a condition description."""

    def __init__(self, path: Path, captions: Path):
        data = json.loads(path.read_text())
        self.scene: str = data["scene"]
        self.conditions: dict[str, str] = data["conditions"]
        self.captions = captions

    def for_job(self, job: Job) -> str:
        caption = self.captions / f"{job.clip}.txt"
        scene = caption.read_text().strip() if caption.exists() else self.scene
        return f"{scene} {self.conditions[job.condition]}"


class ClipPrep:
    """Re-encodes clean clips to a fixed frame rate and optional frame cap with ffmpeg.

    Cosmos keeps the input's frame rate and splits it into 93-frame chunks, so a 30 fps
    clip costs roughly twice as many chunks as the same clip at 16 fps.
    """

    def __init__(self, work: Path, fps: int, max_frames: int | None):
        self.fps = fps
        self.max_frames = max_frames
        self.out_dir = work / "prepared" / f"{fps}fps-{max_frames or 'all'}"

    def prepare(self, src: Path) -> Path:
        dst = self.out_dir / f"{src.stem}.mp4"
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            return dst
        self.out_dir.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(f"{src.stem}.partial.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an",
               "-vf", f"fps={self.fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if self.max_frames:
            cmd += ["-frames:v", str(self.max_frames)]
        subprocess.run([*cmd, str(tmp)], check=True)
        os.replace(tmp, dst)
        return dst

    @staticmethod
    def frames(path: Path) -> int:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True,
        )
        return int(out.stdout.strip().split(",")[0])


@dataclass(frozen=True)
class Settings:
    """Generation knobs shared by every job in a batch."""

    guidance: int = 3  # Cosmos accepts integers 0-7
    seed: int = 2025
    edge_weight: float = 1.0
    edge_threshold: str = "medium"
    distilled: bool = False

    @property
    def model(self) -> str:
        return "edge/distilled" if self.distilled else "edge"

    @property
    def num_steps(self) -> int | None:
        return 4 if self.distilled else None  # distilled is trained for 4 steps; base uses Cosmos' default


class SpecWriter:
    """Writes one Cosmos inference JSON per job. Edge control keeps scene geometry fixed."""

    def __init__(self, out_dir: Path, prompts: Prompts, settings: Settings):
        self.out_dir = out_dir
        self.prompts = prompts
        self.settings = settings

    def spec(self, job: Job, video: Path) -> dict:
        s = self.settings
        spec = {
            "name": job.name,
            "prompt": self.prompts.for_job(job),
            "video_path": str(video.resolve()),
            "guidance": s.guidance,
            "seed": s.seed,
            "edge": {"control_weight": s.edge_weight, "preset_edge_threshold": s.edge_threshold},
        }
        if s.num_steps:
            spec["num_steps"] = s.num_steps
        return spec

    def write(self, job: Job, video: Path) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{job.name}.json"
        path.write_text(json.dumps(self.spec(job, video), indent=2))
        return path
