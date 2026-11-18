"""Fetch FRED data and save it as pinned-fixture candidates.

    uv run --env-file .env python scripts/update_fred_fixture.py [--dataset treasury|mortgage|all]

Writes data/fixtures/fred_treasury_par_<today>.json and/or
data/fixtures/fred_obmmic30yf_<today>.json. Refuses to overwrite an existing
file (use --force). It does not change which fixtures are pinned: that is
PINNED_FIXTURE / PINNED_MORTGAGE_FIXTURE in tenorwise/curve/fixture.py.
Prints no secrets.
"""

import argparse
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
    fetch_observations,
    fetch_par_series,
)
from tenorwise.curve.mortgage_spread import ATTRIBUTION, MORTGAGE_RATE_SERIES  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["treasury", "mortgage", "all"], default="all")
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

    for name, path in jobs:
        if path.exists() and not args.force:
            print(f"exists, not overwriting: {path.relative_to(REPO_ROOT)} (use --force)")
            continue
        if name == "treasury":
            raw = fetch_par_series(api_key, as_of)
            write_fixture(path, as_of, fetched_at, start, as_of, raw)
            par = load_fixture(path).par_curve()
            print(f"wrote {path.relative_to(REPO_ROOT)}; latest complete data date {par.data_date}")
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
