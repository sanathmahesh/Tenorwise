"""2022 replay shock: how much each Treasury par yield rose during 2022.

    shock (bp) = 100 * (FRED value on 2022-12-30 - FRED value on 2021-12-31)

for each of the 11 par-yield series, applied to today's curve (PLAN.md
section 6). Both dates must have a value for every series; nothing is filled.
2022 was the sharpest bond sell-off in decades: short rates rose most as the
Federal Reserve raised its policy rate from near zero.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from tenorwise.curve.fred import PAR_SERIES_IDS, IncompleteDataError, parse_observations
from tenorwise.paths import FIXTURES_DIR

REPLAY_START = date(2021, 12, 31)
REPLAY_END = date(2022, 12, 30)
REPLAY_FIXTURE = FIXTURES_DIR / "fred_treasury_par_replay_2022.json"


def replay_shock_bp(
    start_obs: Mapping[str, Mapping[date, float | None]],
    end_obs: Mapping[str, Mapping[date, float | None]],
) -> tuple[float, ...]:
    """Per-tenor change in percent-point FRED values, in basis points, shortest tenor first."""
    shock = []
    for sid in PAR_SERIES_IDS:
        start = start_obs.get(sid, {}).get(REPLAY_START)
        end = end_obs.get(sid, {}).get(REPLAY_END)
        if start is None or end is None:
            raise IncompleteDataError(f"{sid} has no value on {REPLAY_START} or {REPLAY_END}")
        shock.append(100.0 * (end - start))
    return tuple(shock)


@dataclass(frozen=True)
class ReplayFixture:
    fetched_at: str
    raw_start: dict[str, dict[str, Any]]
    raw_end: dict[str, dict[str, Any]]

    def parsed(self) -> tuple[dict[str, dict[date, float | None]], dict[str, dict[date, float | None]]]:
        return (
            {sid: parse_observations(self.raw_start[sid]) for sid in PAR_SERIES_IDS},
            {sid: parse_observations(self.raw_end[sid]) for sid in PAR_SERIES_IDS},
        )


def load_replay_fixture(path: Path = REPLAY_FIXTURE) -> ReplayFixture:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReplayFixture(
        fetched_at=doc["fetched_at"], raw_start=doc["responses_start"], raw_end=doc["responses_end"]
    )
