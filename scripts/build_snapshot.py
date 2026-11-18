"""Build the static JSON snapshot. Runs locally and in the Vercel build step.

    uv run --env-file .env python scripts/build_snapshot.py   # live FRED (needs FRED_API_KEY); the deploy build
    uv run python scripts/build_snapshot.py --fixture          # pinned fixtures, offline and reproducible
    uv run python scripts/build_snapshot.py --pin              # rewrite the pinned fixture snapshot
                                                               # (data/fixtures/snapshot_v1) used by tests and evals

Writes web/public/data/v1/ (static files) and data/snapshot/v1/ (read by the
API function). If FRED fails, or the data is stale or incomplete, the build
fails and nothing is written. Prints no secrets.
"""

import argparse
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.curve.fixture import load_fixture  # noqa: E402
from tenorwise.curve.fred import FRED_NOTICE  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402
from tenorwise.snapshot.build import EVAL_SUMMARY, FUNCTION_OUT_DIR, WEB_OUT_DIR, build_snapshot  # noqa: E402
from tenorwise.snapshot.inputs import MarketInputs  # noqa: E402

PINNED_SNAPSHOT_DIR = FIXTURES_DIR / "snapshot_v1"


def resolve_git_sha() -> str | None:
    """CLI deploys pass TENORWISE_GIT_SHA; Git-connected deploys set VERCEL_GIT_COMMIT_SHA."""
    for name in ("TENORWISE_GIT_SHA", "VERCEL_GIT_COMMIT_SHA"):
        value = os.environ.get(name)
        if value:
            return value[:7]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--fixture", action="store_true", help="use the pinned fixtures instead of live FRED")
    mode.add_argument("--pin", action="store_true", help="rewrite data/fixtures/snapshot_v1 from the pinned fixtures")
    args = ap.parse_args()

    if args.fixture or args.pin:
        inputs = MarketInputs.from_fixtures()
        build_time = load_fixture().fetched_at  # deterministic for fixture builds
        git_sha = "fixture"
        llm_model = None if args.pin else (os.environ.get("LLM_MODEL") or None)
    else:
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            print("FRED_API_KEY is not set: the live build cannot run (use --fixture for an offline build)", file=sys.stderr)
            return 2
        inputs = MarketInputs.from_fred(api_key, as_of=date.today())
        build_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        git_sha = resolve_git_sha()
        llm_model = os.environ.get("LLM_MODEL") or None

    if args.pin:
        web_dirs, function_dirs = [], [PINNED_SNAPSHOT_DIR]
    else:
        web_dirs, function_dirs = [WEB_OUT_DIR], [FUNCTION_OUT_DIR]
    # The pinned test snapshot carries no eval results, so rerunning evals never changes it.
    eval_summary = None if args.pin else EVAL_SUMMARY
    files = build_snapshot(inputs, web_dirs, function_dirs, build_time, git_sha, llm_model, eval_summary)

    for d in web_dirs + function_dirs:
        print(f"wrote {len(list(Path(d).glob('*.json')))} files -> {Path(d).relative_to(REPO_ROOT)}")
    print(f"source: {inputs.source}; market data date {inputs.par.data_date}; mortgage spread date {inputs.mortgage.date}")
    print(f"build_time={build_time} git_sha={git_sha} llm_model={llm_model} ({len(files)} files)")
    published = eval_summary is not None and eval_summary.exists()
    print(f"eval results in evidence.json: {'yes, from ' + str(eval_summary.relative_to(REPO_ROOT)) if published else 'none'}")
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
