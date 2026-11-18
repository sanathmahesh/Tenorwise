"""Where a command-line tool gets its par curve: the pinned fixture or live FRED."""

from __future__ import annotations

import os
from datetime import date

from tenorwise.curve.bootstrap import ParCurve
from tenorwise.curve.fixture import PINNED_FIXTURE, load_fixture
from tenorwise.curve.fred import fetch_par_series, parse_observations, select_par_curve
from tenorwise.paths import REPO_ROOT


def load_par_curve(live: bool = False) -> tuple[ParCurve, str]:
    """Return (par curve, human-readable description of the source)."""
    if not live:
        fx = load_fixture()
        return fx.par_curve(), (
            f"pinned fixture {PINNED_FIXTURE.relative_to(REPO_ROOT)} (fetched {fx.fetched_at})"
        )
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is not set (use: uv run --env-file .env ...)")
    today = date.today()
    raw = fetch_par_series(api_key, today)
    parsed = {sid: parse_observations(r) for sid, r in raw.items()}
    return select_par_curve(parsed, as_of=today), f"live FRED fetch on {today}"
