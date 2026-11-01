"""Where this environment's venv lives.

A checkout shared by several machines or containers cannot share one venv: it bakes in absolute
paths and platform binaries. Each environment gets `.venvs/<os>-<arch>-<hash of the repo path>`.
Standard library only, because the launcher runs it before any dependency is installed.
"""

import hashlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tag(root: Path) -> str:
    path_hash = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:6]
    return f"{platform.system().lower()}-{platform.machine().lower()}-{path_hash}"


def venv_path(root: Path) -> Path:
    return root / ".venvs" / tag(root)


if __name__ == "__main__":
    sys.stdout.write(f"{venv_path(ROOT)}\n")
