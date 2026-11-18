"""Scenarios: revaluation, AOCI, carry (PLAN.md section 6, Scenarios).

Run on the approved portfolio and the pinned FRED data (2026-11-16).
"""

import numpy as np
import pytest

from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.shocks import parallel_shock
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context, value_portfolio
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.replay import load_replay_fixture, replay_shock_bp
from tenorwise.scenarios.revaluation import run_scenario


@pytest.fixture(scope="module")
def positions():
    return load_positions()


@pytest.fixture(scope="module")
def ctx():
    return build_market_context(fixture_par_curve(), fixture_mortgage_spread())


@pytest.fixture(scope="module")
def presets():
    return {s.id: s for s in preset_scenarios(replay_shock_bp(*load_replay_fixture().parsed()))}


@pytest.fixture(scope="module")
def results(presets, positions, ctx):
    return {sid: run_scenario(s, positions, ctx) for sid, s in presets.items()}


def custom(bp: float) -> Scenario:
    return Scenario(id=f"test_{bp:+g}", name=f"{bp:+g} bp", description="test", shock_bp=tuple(parallel_shock(bp)))


def test_seven_presets_in_plan_order(presets):
    assert list(presets) == [
        "parallel_up_100",
        "parallel_down_100",
        "parallel_up_200",
        "parallel_down_200",
        "bear_steepener",
        "bull_flattener",
        "replay_2022",
    ]


def test_steepener_and_flattener_are_scaled_tents(presets):
    # +25 bp up to 2y, +50 at 5y, +75 at 10y, +100 at 30y; tenors 1M..30Y.
    expected = [25, 25, 25, 25, 25, 100 / 3, 50, 60, 75, 87.5, 100]
    np.testing.assert_allclose(presets["bear_steepener"].shock_bp, expected, atol=1e-12)
    np.testing.assert_allclose(presets["bull_flattener"].shock_bp, [-x for x in expected], atol=1e-12)


def test_zero_shock_changes_nothing(positions, ctx):
    r = run_scenario(custom(0.0), positions, ctx)
    base_carry = run_scenario(custom(0.0), positions, ctx).total.carry_12m

    assert r.total.delta_mv == 0.0
    assert r.total.aoci_impact == 0.0
    assert r.total.htm_unrecognized == 0.0
    assert all(p.delta_mv == 0.0 for p in r.positions)
    assert r.total.carry_12m == base_carry
    assert r.floor_bound is False


@pytest.mark.parametrize("bp", [1.0, -1.0])
def test_one_bp_shift_matches_dv01(positions, ctx, bp):
    dv01 = value_portfolio(positions, ctx).summary.dv01
    r = run_scenario(custom(bp), positions, ctx)

    assert -r.total.delta_mv / bp == pytest.approx(dv01, rel=1e-2)


def test_change_in_value_is_ordered(results):
    d = {k: results[k].total.delta_mv for k in ("parallel_down_200", "parallel_down_100", "parallel_up_100", "parallel_up_200")}
    assert d["parallel_down_200"] > d["parallel_down_100"] > 0 > d["parallel_up_100"] > d["parallel_up_200"]


def test_aoci_impact_equals_the_afs_change_and_excludes_htm(results):
    for r in results.values():
        afs = sum(p.delta_mv for p in r.positions if p.position.klass == "AFS")
        htm = sum(p.delta_mv for p in r.positions if p.position.klass == "HTM")
        assert r.total.aoci_impact == pytest.approx(afs, abs=1e-9)
        assert r.total.htm_unrecognized == pytest.approx(htm, abs=1e-9)
        assert r.total.delta_mv == pytest.approx(afs + htm, abs=1e-9)
        assert r.by_class["AFS"].aoci_impact == pytest.approx(afs, abs=1e-9)
        assert r.by_class["HTM"].aoci_impact == 0.0
        assert r.by_class["AFS"].htm_unrecognized == 0.0


def test_near_the_money_pool_gains_less_at_minus_100_than_it_loses_at_plus_100(results, ctx):
    """D-042: negative convexity is tested where it lives, on pools whose WAC is
    within 0.5 percentage point of today's mortgage rate."""
    mortgage_rate = ctx.base.par.par_yields[ctx.base.par.tenor_months.index(120)] + ctx.mortgage.spread
    down = {p.position.id: p.delta_mv for p in results["parallel_down_100"].positions}
    up = {p.position.id: p.delta_mv for p in results["parallel_up_100"].positions}
    near = [
        p.position.id
        for p in results["parallel_up_100"].positions
        if p.position.kind == "mbs" and abs(p.position.instrument.wac - mortgage_rate) <= 0.005
    ]

    assert near, "no pool within 0.5 pp of today's mortgage rate"
    for pid in near:
        assert 0 < down[pid] < -up[pid], (pid, down[pid], up[pid])


def test_mortgage_sleeve_asymmetry_is_reported(results):
    """Reported, not asserted (D-042): on 16 Nov 2026 the BNY-like sleeve is
    positively convex because most pools are far out of the money."""
    gain = results["parallel_down_100"].by_sector["agency_mbs"].delta_mv
    loss = -results["parallel_up_100"].by_sector["agency_mbs"].delta_mv

    assert gain > 0 and loss > 0


def test_steepener_loses_and_flattener_gains(results):
    assert results["bear_steepener"].total.delta_mv < 0
    assert results["bull_flattener"].total.delta_mv > 0


def test_bullet_bond_carry_is_amortized_cost_times_book_yield(results):
    for r in results.values():
        for p in r.positions:
            if p.position.kind == "bond":
                months = min(12, p.position.maturity_months)
                expected = p.position.amortized_cost * p.position.book_yield * months / 12
                assert p.carry_12m == pytest.approx(expected, rel=1e-13), p.position.id


def test_mortgage_carry_falls_in_rallies(results, positions, ctx):
    base = run_scenario(custom(0.0), positions, ctx).by_sector["agency_mbs"].carry_12m
    down_100 = results["parallel_down_100"].by_sector["agency_mbs"].carry_12m
    down_200 = results["parallel_down_200"].by_sector["agency_mbs"].carry_12m

    assert down_200 < down_100 < base


def test_zero_floor_is_flagged_when_it_binds(positions, ctx, results):
    deep = run_scenario(custom(-450.0), positions, ctx)

    assert deep.floor_bound is True
    assert deep.floored_tenor_months[:3] == (1, 3, 6)
    assert all(r.floor_bound is False for r in results.values())


def test_groups_add_up(results):
    for r in results.values():
        for grouping in ("by_sector", "by_class"):
            groups = getattr(r, grouping).values()
            assert sum(g.delta_mv for g in groups) == pytest.approx(r.total.delta_mv, abs=1e-9)
            assert sum(g.carry_12m for g in groups) == pytest.approx(r.total.carry_12m, abs=1e-9)
