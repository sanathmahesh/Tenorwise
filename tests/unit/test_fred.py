"""FRED client: parsing, latest-complete-date selection, staleness, key safety.

All observation values here are synthetic test inputs, not market data.
No network: HTTP is replaced by httpx.MockTransport.
"""

from datetime import date

import httpx
import pytest

from tenorwise.curve.fred import (
    MAX_DATA_AGE_DAYS,
    PAR_SERIES,
    FredError,
    IncompleteDataError,
    StaleDataError,
    fetch_observations,
    latest_complete_date,
    parse_observations,
    select_par_curve,
)

SERIES_IDS = [sid for sid, _ in PAR_SERIES]


def raw_response(points: dict[str, str]) -> dict:
    """Shape of a FRED series/observations JSON response."""
    return {
        "realtime_start": "2000-01-31",
        "realtime_end": "2000-01-31",
        "observations": [
            {"realtime_start": "2000-01-31", "realtime_end": "2000-01-31", "date": d, "value": v}
            for d, v in points.items()
        ],
    }


def all_series(points: dict[str, str]) -> dict[str, dict]:
    return {sid: parse_observations(raw_response(points)) for sid in SERIES_IDS}


# ---------------------------------------------------------------- parsing


def test_parser_turns_dot_into_missing_and_numbers_into_floats():
    parsed = parse_observations(raw_response({"2000-01-03": "4.25", "2000-01-04": "."}))

    assert parsed == {date(2000, 1, 3): 4.25, date(2000, 1, 4): None}


def test_latest_complete_date_skips_dates_where_any_series_is_missing():
    series = all_series({"2000-01-03": "4.00", "2000-01-04": "4.10", "2000-01-05": "4.20"})
    # One series has "." on the latest date: that date is incomplete.
    series["DGS7"] = parse_observations(
        raw_response({"2000-01-03": "4.00", "2000-01-04": "4.10", "2000-01-05": "."})
    )
    # Another series has no row at all for the latest date.
    series["DGS1MO"] = parse_observations(raw_response({"2000-01-03": "4.00", "2000-01-04": "4.10"}))

    assert latest_complete_date(series) == date(2000, 1, 4)


def test_no_forward_fill_when_a_series_is_missing_on_every_recent_date():
    series = all_series({"2000-01-03": "4.00", "2000-01-04": "4.10"})
    series["DGS20"] = parse_observations(raw_response({"2000-01-03": ".", "2000-01-04": "."}))

    assert latest_complete_date(series) is None
    with pytest.raises(IncompleteDataError):
        select_par_curve(series, as_of=date(2000, 1, 5))


def test_select_par_curve_returns_decimals_in_tenor_order():
    series = all_series({"2000-01-03": "4.00"})
    series["DGS10"] = parse_observations(raw_response({"2000-01-03": "4.37"}))

    par = select_par_curve(series, as_of=date(2000, 1, 4))

    assert par.data_date == date(2000, 1, 3)
    assert par.tenor_months == tuple(m for _, m in PAR_SERIES)
    assert par.par_yields[SERIES_IDS.index("DGS10")] == pytest.approx(0.0437, abs=1e-15)
    assert par.par_yields[0] == pytest.approx(0.04, abs=1e-15)


# ---------------------------------------------------------------- staleness


def test_stale_data_fails():
    series = all_series({"2000-01-03": "4.00"})

    with pytest.raises(StaleDataError):
        select_par_curve(series, as_of=date(2000, 1, 3 + MAX_DATA_AGE_DAYS + 1))


def test_data_exactly_at_the_age_limit_is_accepted():
    series = all_series({"2000-01-03": "4.00"})

    par = select_par_curve(series, as_of=date(2000, 1, 3 + MAX_DATA_AGE_DAYS))

    assert par.data_date == date(2000, 1, 3)


# ---------------------------------------------------------------- HTTP client

SECRET = "abcdefghijklmnopqrstuvwxyz123456"  # synthetic 32-char key for tests


def test_fetch_sends_expected_query():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        seen["path"] = request.url.path
        return httpx.Response(200, json=raw_response({"2000-01-03": "4.00"}))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    raw = fetch_observations("DGS10", SECRET, date(2000, 1, 1), date(2000, 1, 31), client=client)

    assert raw["observations"][0]["value"] == "4.00"
    assert seen["path"] == "/fred/series/observations"
    assert seen["series_id"] == "DGS10"
    assert seen["file_type"] == "json"
    assert seen["observation_start"] == "2000-01-01"
    assert seen["observation_end"] == "2000-01-31"
    assert seen["api_key"] == SECRET


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, text="server error"),
        lambda request: httpx.Response(
            400, json={"error_code": 400, "error_message": f"Bad Request. api_key {SECRET} not registered"}
        ),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("boom", request=request)),
    ],
    ids=["http-500", "http-400-echoing-key", "network-error"],
)
def test_fetch_errors_never_contain_the_api_key(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(FredError) as excinfo:
        fetch_observations("DGS10", SECRET, date(2000, 1, 1), date(2000, 1, 31), client=client)

    rendered = str(excinfo.value) + repr(excinfo.value) + str(excinfo.value.__cause__)
    assert SECRET not in rendered
    assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__
