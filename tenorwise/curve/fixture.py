"""Pinned FRED data for tests and evals, so results are reproducible.

A fixture file stores FRED's raw JSON responses exactly as received (no API
key is stored), plus the date it was fetched. The fetch date stands in for the
build date in the staleness check, so a pinned fixture never goes stale.

Create a new fixture with scripts/update_fred_fixture.py. Changing which
fixture is pinned is a deliberate code change to PINNED_FIXTURE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from tenorwise.curve.bootstrap import ParCurve
from tenorwise.curve.fred import (
    FRED_OBSERVATIONS_URL,
    PAR_SERIES_IDS,
    parse_observations,
    select_par_curve,
)
from tenorwise.paths import FIXTURES_DIR

PINNED_FIXTURE = FIXTURES_DIR / "fred_treasury_par_2026-11-17.json"


@dataclass(frozen=True)
class FredFixture:
    as_of: date
    fetched_at: str
    observation_start: date
    observation_end: date
    raw: dict[str, dict[str, Any]]

    def parsed(self) -> dict[str, dict[date, float | None]]:
        return {sid: parse_observations(self.raw[sid]) for sid in PAR_SERIES_IDS}

    def par_curve(self) -> ParCurve:
        return select_par_curve(self.parsed(), as_of=self.as_of)


def load_fixture(path: Path = PINNED_FIXTURE) -> FredFixture:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return FredFixture(
        as_of=date.fromisoformat(doc["as_of"]),
        fetched_at=doc["fetched_at"],
        observation_start=date.fromisoformat(doc["observation_start"]),
        observation_end=date.fromisoformat(doc["observation_end"]),
        raw=doc["responses"],
    )


def fixture_par_curve(path: Path = PINNED_FIXTURE) -> ParCurve:
    return load_fixture(path).par_curve()


def write_fixture(
    path: Path,
    as_of: date,
    fetched_at: str,
    observation_start: date,
    observation_end: date,
    raw: dict[str, dict[str, Any]],
) -> None:
    doc = {
        "description": "Raw FRED series/observations responses for the 11 Treasury par-yield series",
        "source": FRED_OBSERVATIONS_URL,
        "as_of": as_of.isoformat(),
        "fetched_at": fetched_at,
        "observation_start": observation_start.isoformat(),
        "observation_end": observation_end.isoformat(),
        "responses": raw,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
