"""FRED client for US Treasury par yields (PLAN.md section 6, Curve).

Source: FRED series DGS1MO ... DGS30, "Market Yield on U.S. Treasury
Securities at N Constant Maturity, Quoted on an Investment Basis", from the
Federal Reserve's H.15 release. Units: percent. Missing days (for example bond
market holidays) come back as the string ".".

Rules:
  - use the most recent date on which all 11 series have a value;
  - never fill forward;
  - refuse data more than MAX_DATA_AGE_DAYS before the build date.

The API key travels only as a query parameter to FRED. Error messages are
built here, never copied from httpx (whose messages can include the URL), and
are scrubbed of the key.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

import httpx

from tenorwise.curve.bootstrap import ParCurve

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_TERMS_URL = "https://fred.stlouisfed.org/docs/api/terms_of_use.html"
# Required by the FRED API Terms of Use (read 2026-11-17).
FRED_NOTICE = (
    "This product uses the FRED® API but is not endorsed or certified by "
    "the Federal Reserve Bank of St. Louis."
)

# (FRED series ID, tenor in whole months), shortest first.
PAR_SERIES: tuple[tuple[str, int], ...] = (
    ("DGS1MO", 1),
    ("DGS3MO", 3),
    ("DGS6MO", 6),
    ("DGS1", 12),
    ("DGS2", 24),
    ("DGS3", 36),
    ("DGS5", 60),
    ("DGS7", 84),
    ("DGS10", 120),
    ("DGS20", 240),
    ("DGS30", 360),
)
PAR_SERIES_IDS: tuple[str, ...] = tuple(sid for sid, _ in PAR_SERIES)
PAR_TENOR_MONTHS: tuple[int, ...] = tuple(m for _, m in PAR_SERIES)

MAX_DATA_AGE_DAYS = 7
DEFAULT_LOOKBACK_DAYS = 45
REQUEST_TIMEOUT_S = 30.0

MISSING = "."


class FredError(Exception):
    """A FRED request failed. The message never contains the API key."""


class CurveDataError(Exception):
    """The FRED data cannot produce a valid curve."""


class IncompleteDataError(CurveDataError):
    """No date has a value for every one of the 11 series."""


class StaleDataError(CurveDataError):
    """The latest complete date is too old to build on."""


# ------------------------------------------------------------------ HTTP


def fetch_observations(
    series_id: str,
    api_key: str,
    observation_start: date,
    observation_end: date,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Return FRED's raw JSON response for one series over a date window."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start.isoformat(),
        "observation_end": observation_end.isoformat(),
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=REQUEST_TIMEOUT_S)
    try:
        try:
            response = http.get(FRED_OBSERVATIONS_URL, params=params)
        except httpx.HTTPError as exc:
            message = f"FRED request for {series_id} failed: {type(exc).__name__}: {exc}"
            raise FredError(_scrub(message, api_key)) from None
        if response.status_code != 200:
            message = (
                f"FRED request for {series_id} failed: HTTP {response.status_code}"
                f" {_error_detail(response)}"
            )
            raise FredError(_scrub(message, api_key)) from None
        try:
            body = response.json()
        except ValueError:
            raise FredError(f"FRED response for {series_id} was not JSON") from None
        if not isinstance(body, dict) or not isinstance(body.get("observations"), list):
            raise FredError(f"FRED response for {series_id} has no observations list") from None
        return body
    finally:
        if owns_client:
            http.close()


def fetch_par_series(
    api_key: str,
    as_of: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    client: httpx.Client | None = None,
) -> dict[str, dict[str, Any]]:
    """Raw responses for all 11 par-yield series over [as_of - lookback, as_of]."""
    start = as_of - timedelta(days=lookback_days)
    return {
        sid: fetch_observations(sid, api_key, start, as_of, client=client) for sid in PAR_SERIES_IDS
    }


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict) and "error_message" in body:
        return str(body["error_message"])[:300]
    return ""


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


# --------------------------------------------------------------- parsing


def parse_observations(raw: Mapping[str, Any]) -> dict[date, float | None]:
    """Map observation date to value in percent; FRED's "." becomes None."""
    out: dict[date, float | None] = {}
    for obs in raw["observations"]:
        day = date.fromisoformat(obs["date"])
        value = obs["value"]
        if value == MISSING:
            out[day] = None
            continue
        try:
            out[day] = float(value)
        except (TypeError, ValueError):
            raise CurveDataError(f"unexpected FRED value {value!r} on {day}") from None
    return out


def latest_complete_date(
    series: Mapping[str, Mapping[date, float | None]],
    series_ids: tuple[str, ...] = PAR_SERIES_IDS,
) -> date | None:
    """Most recent date on which every series has a numeric value (no filling)."""
    missing = [sid for sid in series_ids if sid not in series]
    if missing:
        raise IncompleteDataError(f"series not fetched: {missing}")
    complete: set[date] | None = None
    for sid in series_ids:
        days = {d for d, v in series[sid].items() if v is not None}
        complete = days if complete is None else complete & days
    return max(complete) if complete else None


def select_par_curve(
    series: Mapping[str, Mapping[date, float | None]],
    as_of: date,
    max_age_days: int = MAX_DATA_AGE_DAYS,
) -> ParCurve:
    """Build the par curve for the latest complete date, refusing stale data."""
    data_date = latest_complete_date(series)
    if data_date is None:
        raise IncompleteDataError("no date on which all 11 Treasury par-yield series have values")
    age = (as_of - data_date).days
    if age < 0:
        raise CurveDataError(f"data date {data_date} is after the build date {as_of}")
    if age > max_age_days:
        raise StaleDataError(
            f"latest complete data date {data_date} is {age} days before {as_of}"
            f" (limit {max_age_days})"
        )
    yields = tuple(series[sid][data_date] / 100.0 for sid in PAR_SERIES_IDS)  # percent -> decimal
    return ParCurve(data_date=data_date, tenor_months=PAR_TENOR_MONTHS, par_yields=yields)
