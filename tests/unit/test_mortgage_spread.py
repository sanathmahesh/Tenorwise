"""Mortgage spread = OBMMIC30YF - DGS10 on the same date (PLAN.md section 6, D-031).

Synthetic observations are test inputs, not market data. The fixture test
checks the pinned values against the raw FRED responses directly.
"""

from datetime import date

import pytest

from tenorwise.curve.fixture import (
    PINNED_FIXTURE,
    PINNED_MORTGAGE_FIXTURE,
    fixture_mortgage_spread,
    load_fixture,
)
from tenorwise.curve.fred import CurveDataError, IncompleteDataError, StaleDataError
from tenorwise.curve.mortgage_spread import (
    MAX_SPREAD_AGE_DAYS,
    MORTGAGE_RATE_SERIES,
    select_mortgage_spread,
)

D = date


def test_uses_the_latest_date_on_which_both_series_have_values():
    mortgage = {D(2000, 1, 3): 6.50, D(2000, 1, 4): 6.55, D(2000, 1, 5): 6.60}
    ten_year = {D(2000, 1, 3): 4.00, D(2000, 1, 4): 4.10, D(2000, 1, 5): None}

    s = select_mortgage_spread(mortgage, ten_year, as_of=D(2000, 1, 6))

    assert s.date == D(2000, 1, 4)
    assert s.mortgage_rate == pytest.approx(0.0655, abs=1e-15)
    assert s.ten_year_yield == pytest.approx(0.0410, abs=1e-15)
    assert s.spread == pytest.approx(0.0245, abs=1e-15)


def test_no_forward_fill_when_dates_never_coincide():
    mortgage = {D(2000, 1, 3): 6.50, D(2000, 1, 4): None}
    ten_year = {D(2000, 1, 3): None, D(2000, 1, 4): 4.10}

    with pytest.raises(IncompleteDataError):
        select_mortgage_spread(mortgage, ten_year, as_of=D(2000, 1, 5))


def test_stale_mortgage_spread_fails():
    mortgage = {D(2000, 1, 3): 6.50}
    ten_year = {D(2000, 1, 3): 4.00}

    with pytest.raises(StaleDataError):
        select_mortgage_spread(mortgage, ten_year, as_of=D(2000, 1, 3 + MAX_SPREAD_AGE_DAYS + 1))
    assert select_mortgage_spread(mortgage, ten_year, as_of=D(2000, 1, 3 + MAX_SPREAD_AGE_DAYS)).date == D(2000, 1, 3)


def test_date_after_build_date_is_rejected():
    with pytest.raises(CurveDataError):
        select_mortgage_spread({D(2000, 1, 9): 6.5}, {D(2000, 1, 9): 4.0}, as_of=D(2000, 1, 5))


def test_pinned_spread_equals_the_raw_fred_values():
    s = fixture_mortgage_spread()
    mortgage_raw = load_fixture(PINNED_MORTGAGE_FIXTURE).raw[MORTGAGE_RATE_SERIES]["observations"]
    ten_year_raw = load_fixture(PINNED_FIXTURE).raw["DGS10"]["observations"]
    m = {o["date"]: o["value"] for o in mortgage_raw}
    t = {o["date"]: o["value"] for o in ten_year_raw}

    assert s.mortgage_rate == pytest.approx(float(m[s.date.isoformat()]) / 100, abs=1e-15)
    assert s.ten_year_yield == pytest.approx(float(t[s.date.isoformat()]) / 100, abs=1e-15)
    assert s.spread == pytest.approx(s.mortgage_rate - s.ten_year_yield, abs=1e-15)
