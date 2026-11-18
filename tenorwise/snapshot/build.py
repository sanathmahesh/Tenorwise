"""Build-time pre-compute: writes the static JSON snapshot.

Phase 0 version. It writes:
  meta.json         the contract fields from PLAN.md section 8 (no market data yet,
                    so data_date is null and fred_series is empty);
  build_check.json  proof that numpy and scipy ran in the build environment.

The same bytes go to every output directory: one copy the frontend serves as
static files (web/public/data/v1/) and one the API function reads
(data/snapshot/v1/). Serialization is deterministic (sorted keys).
"""

import json
import platform
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tenorwise.snapshot.store import DEFAULT_SNAPSHOT_DIR, REPO_ROOT

WEB_OUT_DIR = REPO_ROOT / "web" / "public" / "data" / "v1"
FUNCTION_OUT_DIR = DEFAULT_SNAPSHOT_DIR


def dumps(obj: Any) -> str:
    """Deterministic JSON: sorted keys, fixed indentation, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def make_meta(build_time: str, git_sha: str | None, llm_model: str | None) -> dict[str, Any]:
    return {
        "data_date": None,
        "build_time": build_time,
        "git_sha": git_sha,
        "fred_series": [],
        "llm_model": llm_model,
        "assumptions": [],
    }


def make_build_check() -> dict[str, Any]:
    """Run numpy and scipy once so the build log proves they work at build time."""
    import numpy as np
    import scipy
    from scipy.optimize import brentq

    root = brentq(lambda x: x * x - 2.0, 0.0, 2.0, xtol=1e-15)
    return {
        "purpose": "Phase 0 deploy check: numpy and scipy ran in the build step",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "brentq_sqrt2": root,
    }


def build_snapshot(
    out_dirs: Iterable[Path],
    build_time: str,
    git_sha: str | None,
    llm_model: str | None,
) -> dict[str, str]:
    files = {
        "meta.json": dumps(make_meta(build_time, git_sha, llm_model)),
        "build_check.json": dumps(make_build_check()),
    }
    for out_dir in out_dirs:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (out_dir / name).write_text(text, encoding="utf-8")
    return files
