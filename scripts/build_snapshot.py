"""Build the static JSON snapshot. Runs locally and in the Vercel build step.

    uv run python scripts/build_snapshot.py

Phase 0: writes meta.json and build_check.json only. Later phases add FRED
data and the engine outputs. Prints no secrets.
"""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.snapshot.build import FUNCTION_OUT_DIR, WEB_OUT_DIR, build_snapshot  # noqa: E402


def resolve_git_sha() -> str | None:
    """CLI deploys pass TENORWISE_GIT_SHA; Git-connected deploys set VERCEL_GIT_COMMIT_SHA."""
    for name in ("TENORWISE_GIT_SHA", "VERCEL_GIT_COMMIT_SHA"):
        value = os.environ.get(name)
        if value:
            return value[:7]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    build_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    git_sha = resolve_git_sha()
    llm_model = os.environ.get("LLM_MODEL") or None
    files = build_snapshot(
        out_dirs=[WEB_OUT_DIR, FUNCTION_OUT_DIR],
        build_time=build_time,
        git_sha=git_sha,
        llm_model=llm_model,
    )
    for out_dir in (WEB_OUT_DIR, FUNCTION_OUT_DIR):
        print(f"wrote {sorted(files)} -> {out_dir.relative_to(REPO_ROOT)}")
    print(f"build_time={build_time} git_sha={git_sha} llm_model={llm_model}")


if __name__ == "__main__":
    main()
