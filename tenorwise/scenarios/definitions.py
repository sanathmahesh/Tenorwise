"""The seven preset scenarios (PLAN.md section 6, Scenarios).

Every scenario is an instantaneous shock to the 11 par yields, after which the
curve is held still. Sector spreads and the mortgage spread do not move.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tenorwise.curve.shocks import key_rate_shock, parallel_shock


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    shock_bp: tuple[float, ...]  # one value per par tenor, shortest first


def _tents(b2: float, b5: float, b10: float, b30: float) -> tuple[float, ...]:
    shock = key_rate_shock(2, b2) + key_rate_shock(5, b5) + key_rate_shock(10, b10) + key_rate_shock(30, b30)
    return tuple(float(x) for x in shock)


def _parallel(bp: float) -> tuple[float, ...]:
    return tuple(float(x) for x in parallel_shock(bp))


def preset_scenarios(replay_2022_bp: Sequence[float]) -> list[Scenario]:
    return [
        Scenario("parallel_up_100", "+100 bp parallel",
                 "Every Treasury par yield rises by 1 percentage point at once.", _parallel(100)),
        Scenario("parallel_down_100", "-100 bp parallel",
                 "Every Treasury par yield falls by 1 percentage point at once.", _parallel(-100)),
        Scenario("parallel_up_200", "+200 bp parallel",
                 "Every Treasury par yield rises by 2 percentage points at once.", _parallel(200)),
        Scenario("parallel_down_200", "-200 bp parallel",
                 "Every Treasury par yield falls by 2 percentage points at once.", _parallel(-200)),
        Scenario("bear_steepener", "Bear steepener",
                 "Rates rise, long rates most: +25 bp up to 2 years, +50 at 5, +75 at 10, +100 at 30, "
                 "straight lines in between.", _tents(25, 50, 75, 100)),
        Scenario("bull_flattener", "Bull flattener",
                 "Rates fall, long rates most: -25 bp up to 2 years, -50 at 5, -75 at 10, -100 at 30, "
                 "straight lines in between.", _tents(-25, -50, -75, -100)),
        Scenario("replay_2022", "2022 replay",
                 "Each Treasury par yield moves by its actual change from 31 Dec 2021 to 30 Dec 2022 "
                 "(FRED), applied to today's curve.", tuple(float(x) for x in replay_2022_bp)),
    ]
