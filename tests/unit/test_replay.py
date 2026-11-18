"""2022 replay: per-tenor change in FRED par yields, 2021-12-31 to 2022-12-30.

Synthetic observations are test inputs. The fixture test checks the shock
against the raw FRED values stored in data/fixtures/.
"""

from datetime import date

import pytest

from tenorwise.curve.fred import PAR_SERIES_IDS, IncompleteDataError
from tenorwise.scenarios.replay import (
    REPLAY_END,
    REPLAY_START,
    load_replay_fixture,
    replay_shock_bp,
)


def test_replay_dates_are_the_plans():
    assert REPLAY_START == date(2021, 12, 31)
    assert REPLAY_END == date(2022, 12, 30)


def test_shock_is_end_minus_start_in_bp():
    start = {sid: {REPLAY_START: 1.00} for sid in PAR_SERIES_IDS}
    end = {sid: {REPLAY_END: 1.25} for sid in PAR_SERIES_IDS}
    end["DGS10"] = {REPLAY_END: 0.50}

    shock = replay_shock_bp(start, end)

    assert shock[PAR_SERIES_IDS.index("DGS10")] == pytest.approx(-50.0, abs=1e-9)
    assert shock[0] == pytest.approx(25.0, abs=1e-9)


def test_missing_value_on_a_replay_date_is_an_error_not_filled():
    start = {sid: {REPLAY_START: 1.00} for sid in PAR_SERIES_IDS}
    end = {sid: {REPLAY_END: 1.25} for sid in PAR_SERIES_IDS}
    end["DGS20"] = {REPLAY_END: None, date(2022, 12, 29): 1.30}

    with pytest.raises(IncompleteDataError):
        replay_shock_bp(start, end)


def test_2022_shock_equals_the_fixture_differences_tenor_by_tenor():
    fx = load_replay_fixture()
    shock = replay_shock_bp(*fx.parsed())
    for i, sid in enumerate(PAR_SERIES_IDS):
        raw_start = {o["date"]: o["value"] for o in fx.raw_start[sid]["observations"]}
        raw_end = {o["date"]: o["value"] for o in fx.raw_end[sid]["observations"]}
        expected = 100.0 * (float(raw_end[REPLAY_END.isoformat()]) - float(raw_start[REPLAY_START.isoformat()]))
        assert shock[i] == pytest.approx(expected, abs=1e-9), sid
