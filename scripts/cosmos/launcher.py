"""Runs Cosmos Transfer 2.5 inference over a batch of spec files and reports the GPU."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


class Cosmos:
    """One inference process per batch, so the model loads once for every pending job.

    SIGTERM/SIGINT (Nebius sends SIGTERM 60 s before stopping a preemptible VM) is
    forwarded to the child and recorded in `interrupted`, so the caller does not count
    the cut-short samples as failures.
    """

    def __init__(self, repo: Path, gpus: int = 1, distilled: bool = False):
        self.repo = repo
        self.gpus = gpus
        self.distilled = distilled
        self.interrupted = False

    def command(self, specs: list[Path], out_dir: Path) -> list[str]:
        venv = self.repo / ".venv" / "bin"
        if self.gpus > 1:
            head = [str(venv / "torchrun"), f"--nproc_per_node={self.gpus}", "--master_port=12341"]
        else:
            head = [str(venv / "python")]
        cmd = [*head, "examples/inference.py", "-i", *map(str, specs), "-o", str(out_dir)]
        return [*cmd, "--model=edge/distilled"] if self.distilled else cmd

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.distilled:
            # The public config registers the distilled edge checkpoint only behind this flag.
            env["COSMOS_EXPERIMENTAL_CHECKPOINTS"] = "1"
        return env

    def run(self, specs: list[Path], out_dir: Path, log: Path) -> int:
        log.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(self.command(specs, out_dir), cwd=self.repo, env=self.env(),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def forward(signum, _frame):
            self.interrupted = True
            proc.send_signal(signum)

        previous = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            with log.open("ab") as sink:
                for line in proc.stdout:
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
                    sink.write(line)
            return proc.wait()
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)

    def commit(self) -> str:
        try:
            out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo,
                                 capture_output=True, text=True)
        except OSError:
            return "unknown"
        return out.stdout.strip() or "unknown"


def gpu_summary() -> str:
    """`<name> <memory> driver <version>` for the first GPU, or "unknown"."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    name, memory, driver = (p.strip() for p in out.stdout.splitlines()[0].split(","))
    return f"{name} {memory} driver {driver}"
