"""Fetch the 11 Treasury par-yield series from FRED and save them as a fixture.

    uv run --env-file .env python scripts/update_fred_fixture.py

Writes data/fixtures/fred_treasury_par_<today>.json. It does not change which
fixture is pinned: that is PINNED_FIXTURE in tenorwise/curve/fixture.py.
Prints no secrets.
"""

import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.curve.fixture import load_fixture, write_fixture  # noqa: E402
from tenorwise.curve.fred import DEFAULT_LOOKBACK_DAYS, FRED_NOTICE, fetch_par_series  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402


def main() -> int:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("FRED_API_KEY is not set (use: uv run --env-file .env ...)", file=sys.stderr)
        return 2
    as_of = date.today()
    start = as_of - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = fetch_par_series(api_key, as_of)
    path = FIXTURES_DIR / f"fred_treasury_par_{as_of.isoformat()}.json"
    write_fixture(path, as_of, fetched_at, start, as_of, raw)

    par = load_fixture(path).par_curve()
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    print(f"as_of {as_of}, latest complete data date {par.data_date}")
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
