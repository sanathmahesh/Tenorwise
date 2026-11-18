"""Market inputs for a snapshot build: from the pinned fixtures or live from FRED.

Three datasets, all via FRED:
  - the 11 Treasury par yields (latest complete date, at most 7 days old);
  - OBMMIC30YF, for the mortgage spread (same-date DGS10);
  - the 11 par yields on 2021-12-31 and 2022-12-30, for the 2022 replay.
A live build fails if any request fails or any rule is broken; nothing is filled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from tenorwise.curve.bootstrap import ParCurve
from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.fred import (
    DEFAULT_LOOKBACK_DAYS,
    PAR_SERIES_IDS,
    REQUEST_TIMEOUT_S,
    fetch_observations,
    parse_observations,
    select_par_curve,
)
from tenorwise.curve.mortgage_spread import (
    MORTGAGE_RATE_SERIES,
    TEN_YEAR_SERIES,
    MortgageSpread,
    select_mortgage_spread,
)
from tenorwise.scenarios.replay import REPLAY_END, REPLAY_START, load_replay_fixture, replay_shock_bp


@dataclass(frozen=True)
class MarketInputs:
    par: ParCurve
    mortgage: MortgageSpread
    replay_shock_bp: tuple[float, ...]
    source: str  # "pinned fixtures" or "FRED"

    @classmethod
    def from_fixtures(cls) -> MarketInputs:
        return cls(
            par=fixture_par_curve(),
            mortgage=fixture_mortgage_spread(),
            replay_shock_bp=replay_shock_bp(*load_replay_fixture().parsed()),
            source="pinned fixtures",
        )

    @classmethod
    def from_fred(cls, api_key: str, as_of: date) -> MarketInputs:
        start = as_of - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
            par_obs = {
                sid: parse_observations(fetch_observations(sid, api_key, start, as_of, client=client))
                for sid in PAR_SERIES_IDS
            }
            mortgage_obs = parse_observations(
                fetch_observations(MORTGAGE_RATE_SERIES, api_key, start, as_of, client=client)
            )
            replay_start = {
                sid: parse_observations(
                    fetch_observations(sid, api_key, REPLAY_START - timedelta(days=7), REPLAY_START, client=client)
                )
                for sid in PAR_SERIES_IDS
            }
            replay_end = {
                sid: parse_observations(
                    fetch_observations(sid, api_key, REPLAY_END - timedelta(days=7), REPLAY_END, client=client)
                )
                for sid in PAR_SERIES_IDS
            }
        return cls(
            par=select_par_curve(par_obs, as_of=as_of),
            mortgage=select_mortgage_spread(mortgage_obs, par_obs[TEN_YEAR_SERIES], as_of=as_of),
            replay_shock_bp=replay_shock_bp(replay_start, replay_end),
            source="FRED",
        )
