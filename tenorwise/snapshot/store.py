"""Read-only access to the build-time snapshot, used by the API function.

The build step (scripts/build_snapshot.py) writes JSON files into
data/snapshot/v1/. The function reads them on every request: nothing is cached
in memory between requests and nothing is written at runtime (ground rule 7).
"""

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshot" / "v1"

# Lets tests point the API at a temporary snapshot.
SNAPSHOT_DIR_ENV = "TENORWISE_SNAPSHOT_DIR"


def snapshot_dir() -> Path:
    override = os.environ.get(SNAPSHOT_DIR_ENV)
    return Path(override) if override else DEFAULT_SNAPSHOT_DIR


def read_json(name: str) -> Any | None:
    """Return the parsed snapshot file, or None if the build has not produced it."""
    path = snapshot_dir() / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
