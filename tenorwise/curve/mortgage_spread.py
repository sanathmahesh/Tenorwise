"""Mortgage spread: the gap between the market mortgage rate and the 10-year Treasury.

    mortgage spread = OBMMIC30YF - DGS10, on the latest date both have a value

OBMMIC30YF is Optimal Blue's 30-Year Fixed Rate Conforming Mortgage Index
(daily, percent), published on FRED. It replaced Freddie Mac's MORTGAGE30US,
whose terms forbid publishing the data or derived products (decision log D-031).

The spread is held fixed in every scenario: a scenario's mortgage rate is its
10-year par yield plus this spread (PLAN.md section 6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from tenorwise.curve.fred import CurveDataError, IncompleteDataError, StaleDataError

MORTGAGE_RATE_SERIES = "OBMMIC30YF"
TEN_YEAR_SERIES = "DGS10"
MAX_SPREAD_AGE_DAYS = 7
ATTRIBUTION = (
    "Mortgage rate: Optimal Blue Mortgage Market Indices (OBMMI™), "
    "30-Year Fixed Rate Conforming Mortgage Index (OBMMIC30YF), via FRED."
)


@dataclass(frozen=True)
class MortgageSpread:
    date: date
    mortgage_rate: float  # decimal
    ten_year_yield: float  # decimal, DGS10 on the same date
    spread: float  # decimal, mortgage_rate - ten_year_yield


def select_mortgage_spread(
    mortgage_obs: Mapping[date, float | None],
    ten_year_obs: Mapping[date, float | None],
    as_of: date,
    max_age_days: int = MAX_SPREAD_AGE_DAYS,
) -> MortgageSpread:
    """Inputs in percent, as FRED reports them; output in decimals. No filling."""
    both = {d for d, v in mortgage_obs.items() if v is not None} & {
        d for d, v in ten_year_obs.items() if v is not None
    }
    if not both:
        raise IncompleteDataError(
            f"no date on which both {MORTGAGE_RATE_SERIES} and {TEN_YEAR_SERIES} have values"
        )
    day = max(both)
    age = (as_of - day).days
    if age < 0:
        raise CurveDataError(f"mortgage spread date {day} is after the build date {as_of}")
    if age > max_age_days:
        raise StaleDataError(f"latest mortgage spread date {day} is {age} days before {as_of}")
    mortgage = mortgage_obs[day] / 100.0
    ten_year = ten_year_obs[day] / 100.0
    return MortgageSpread(date=day, mortgage_rate=mortgage, ten_year_yield=ten_year, spread=mortgage - ten_year)
