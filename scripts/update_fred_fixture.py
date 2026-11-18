"""Fetch FRED data and save it as pinned-fixture candidates.

    uv run --env-file .env python scripts/update_fred_fixture.py [--dataset treasury|mortgage|replay2022|all]

Writes data/fixtures/fred_treasury_par_<today>.json, data/fixtures/fred_obmmic30yf_<today>.json
and/or data/fixtures/fred_treasury_par_replay_2022.json (the 11 par-yield series around
2021-12-31 and 2022-12-30, for the 2022 replay scenario). Refuses to overwrite an existing
file (use --force). It does not change which fixtures are pinned: that is
PINNED_FIXTURE / PINNED_MORTGAGE_FIXTURE in tenorwise/curve/fixture.py.
Prints no secrets.
"""

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.curve.fixture import load_fixture, write_fixture  # noqa: E402
from tenorwise.curve.fred import (  # noqa: E402
    DEFAULT_LOOKBACK_DAYS,
    FRED_NOTICE,
    FRED_OBSERVATIONS_URL,
    PAR_SERIES_IDS,
    fetch_observations,
    fetch_par_series,
)
from tenorwise.scenarios.replay import (  # noqa: E402
    REPLAY_END,
    REPLAY_FIXTURE,
    REPLAY_START,
    load_replay_fixture,
    replay_shock_bp,
)
from tenorwise.curve.mortgage_spread import ATTRIBUTION, MORTGAGE_RATE_SERIES  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["treasury", "mortgage", "replay2022", "all"], default="all")
    ap.add_argument("--force", action="store_true", help="overwrite an existing fixture file")
    args = ap.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("FRED_API_KEY is not set (use: uv run --env-file .env ...)", file=sys.stderr)
        return 2
    as_of = date.today()
    start = as_of - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    jobs = []
    if args.dataset in ("treasury", "all"):
        jobs.append(("treasury", FIXTURES_DIR / f"fred_treasury_par_{as_of.isoformat()}.json"))
    if args.dataset in ("mortgage", "all"):
        jobs.append(("mortgage", FIXTURES_DIR / f"fred_obmmic30yf_{as_of.isoformat()}.json"))
    if args.dataset in ("replay2022", "all"):
        jobs.append(("replay2022", REPLAY_FIXTURE))

    for name, path in jobs:
        if path.exists() and not args.force:
            print(f"exists, not overwriting: {path.relative_to(REPO_ROOT)} (use --force)")
            continue
        if name == "treasury":
            raw = fetch_par_series(api_key, as_of)
            write_fixture(path, as_of, fetched_at, start, as_of, raw)
            par = load_fixture(path).par_curve()
            print(f"wrote {path.relative_to(REPO_ROOT)}; latest complete data date {par.data_date}")
        elif name == "replay2022":
            windows = {
                "start": (REPLAY_START - timedelta(days=7), REPLAY_START + timedelta(days=3)),
                "end": (REPLAY_END - timedelta(days=7), REPLAY_END + timedelta(days=4)),
            }
            doc = {
                "description": "Raw FRED series/observations responses for the 11 Treasury par-yield series around "
                f"{REPLAY_START} and {REPLAY_END}, for the 2022 replay scenario",
                "source": FRED_OBSERVATIONS_URL,
                "fetched_at": fetched_at,
                "replay_start": REPLAY_START.isoformat(),
                "replay_end": REPLAY_END.isoformat(),
                "windows": {k: [a.isoformat(), b.isoformat()] for k, (a, b) in windows.items()},
            }
            for key, (a, b) in windows.items():
                doc[f"responses_{key}"] = {sid: fetch_observations(sid, api_key, a, b) for sid in PAR_SERIES_IDS}
            path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            shock = replay_shock_bp(*load_replay_fixture(path).parsed())
            print(f"wrote {path.relative_to(REPO_ROOT)}; replay shock (bp): " + ", ".join(f"{x:+.0f}" for x in shock))
        else:
            raw = {MORTGAGE_RATE_SERIES: fetch_observations(MORTGAGE_RATE_SERIES, api_key, start, as_of)}
            write_fixture(
                path, as_of, fetched_at, start, as_of, raw,
                description=f"Raw FRED series/observations response for {MORTGAGE_RATE_SERIES}. {ATTRIBUTION}",
            )
            obs = [o for o in raw[MORTGAGE_RATE_SERIES]["observations"] if o["value"] != "."]
            print(f"wrote {path.relative_to(REPO_ROOT)}; latest {MORTGAGE_RATE_SERIES} date {obs[-1]['date'] if obs else None}")
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
