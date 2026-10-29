"""Forward the IMPLEMENT.md entry point to the shared Cosmos batch runner."""

import os
import sys
from pathlib import Path


if __name__ == "__main__":
    runner = Path(__file__).resolve().parent.parent / "cosmos" / "run.py"
    os.execv(sys.executable, [sys.executable, str(runner), *sys.argv[1:]])
