"""Hedging strategies against the AFS book (PLAN.md section 7).

Thresholds fixed before the first run:
  - DV01 hedges leave exactly the intended DV01 (sized with the same measure): 1e-9 relative;
  - "near flat" for +/-10 bp: the hedged AFS + swap change is within 2% of the
    unhedged AFS change (second-order terms at 10 bp are about 0.5%);
  - key-rate buckets zeroed to 1e-9 of the AFS DV01.
"""

import pytest

from tenorwise.analytics.risk import dollar_convexity
from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.shocks import parallel_shock
from tenorwise.hedging.grid import run_grid
from tenorwise.hedging.strategies import afs_risk, build_strategies
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context, price_function, value_portfolio
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.replay import load_replay_fixture, replay_shock_bp


def parallel(bp):
    return Scenario(f"p{bp:+g}", f"{bp:+g} bp", "test", tuple(parallel_shock(bp)))


@pytest.fixture(scope="module")
def positions():
    return load_positions()


@pytest.fixture(scope="module")
def ctx():
    return build_market_context(fixture_par_curve(), fixture_mortgage_spread())


@pytest.fixture(scope="module")
def pv(positions, ctx):
    return value_portfolio(positions, ctx)


@pytest.fixture(scope="module")
def strategies(pv, ctx):
    return {s.id: s for s in build_strategies(pv, ctx, swap_spread=0.0)}


@pytest.fixture(scope="module")
def scenarios():
    presets = preset_scenarios(replay_shock_bp(*load_replay_fixture().parsed()))
    return presets + [parallel(10.0), parallel(-10.0)]


@pytest.fixture(scope="module")
def grid(strategies, scenarios, positions, ctx):
    return run_grid(list(strategies.values()), scenarios, positions, ctx)


def cell(grid, strategy_id, scenario_id):
    return next(c for c in grid if c.strategy_id == strategy_id and c.scenario_id == scenario_id)


def test_four_strategies(strategies):
    assert list(strategies) == ["unhedged", "dv01_50", "dv01_full", "key_rate"]
    assert strategies["unhedged"].swaps == ()
    assert [s.tenor_months for s in strategies["dv01_50"].swaps] == [60]
    assert [s.tenor_months for s in strategies["dv01_full"].swaps] == [60]
    assert [s.tenor_months for s in strategies["key_rate"].swaps] == [24, 60, 120]


def test_50pct_hedge_leaves_half_the_afs_dv01_and_the_full_hedge_about_none(strategies, pv):
    afs = afs_risk(pv).dv01
    assert strategies["dv01_50"].dv01_after == pytest.approx(0.5 * afs, rel=1e-9)
    assert abs(strategies["dv01_full"].dv01_after) < 1e-9 * afs
    assert strategies["unhedged"].dv01_after == pytest.approx(afs, rel=1e-15)


def test_full_dv01_hedge_is_near_flat_for_small_parallel_moves(grid):
    for sid in ("p+10", "p-10"):
        unhedged = cell(grid, "unhedged", sid).aoci_net
        hedged = cell(grid, "dv01_full", sid).aoci_net
        assert abs(hedged) <= 0.02 * abs(unhedged), (sid, hedged, unhedged)


def test_full_dv01_hedge_leaves_a_residual_loss_in_the_bear_steepener(grid):
    assert cell(grid, "dv01_full", "bear_steepener").aoci_net < 0


def test_key_rate_hedge_zeroes_2y_5y_and_the_10y_plus_30y_total(strategies, pv):
    afs = afs_risk(pv).dv01
    after = strategies["key_rate"].key_rate_dv01_after
    assert abs(after[2]) < 1e-9 * afs
    assert abs(after[5]) < 1e-9 * afs
    assert abs(after[10] + after[30]) < 1e-9 * afs


def test_key_rate_hedge_has_a_smaller_steepener_residual_than_the_full_dv01_hedge(grid):
    kr = cell(grid, "key_rate", "bear_steepener").aoci_net
    full = cell(grid, "dv01_full", "bear_steepener").aoci_net
    assert abs(kr) < abs(full), (kr, full)


def hedged_dollar_convexity(strategy, positions, ctx):
    """AFS book plus the strategy's swaps, second difference over +/-25 bp."""
    afs = [p for p in positions if p.klass == "AFS"]

    def value(curve):
        return sum(price_function(p, ctx)(curve) for p in afs) + sum(s.value(curve) for s in strategy.swaps)

    return dollar_convexity(value, ctx.curves)


def test_full_hedge_residual_at_plus_200_has_the_sign_of_the_hedged_books_convexity(grid, strategies, positions, ctx):
    """D-046 (1). Where prepayments do not respond, convexity predicts the residual."""
    c_net = hedged_dollar_convexity(strategies["dv01_full"], positions, ctx)
    residual = cell(grid, "dv01_full", "parallel_up_200").aoci_net
    assert residual * c_net > 0, (residual, c_net)


def test_full_hedge_residual_at_minus_200_falls_short_of_the_convexity_prediction(grid, strategies, positions, ctx):
    """D-046 (2), reported: in a large rally near-the-money pools prepay, the AFS
    duration shortens below the swap's, and the static hedge is too large."""
    c_net = hedged_dollar_convexity(strategies["dv01_full"], positions, ctx)
    predicted = 0.5 * c_net * (200e-4) ** 2
    residual = cell(grid, "dv01_full", "parallel_down_200").aoci_net
    assert residual < predicted, (residual, predicted)


def test_control_without_mortgage_pools_the_200bp_residual_has_the_sign_of_afs_convexity(ctx):
    """D-046 (3): the plan's original statement, tested where it applies."""
    positions = [p for p in load_positions() if not (p.klass == "AFS" and p.kind == "mbs")]
    pv = value_portfolio(positions, ctx)
    full = build_strategies(pv, ctx)[2]
    grid = run_grid([full], [parallel(200.0), parallel(-200.0)], positions, ctx)
    afs_convexity = afs_risk(pv).convexity
    for c in grid:
        assert c.aoci_net * afs_convexity > 0, (c.scenario_id, c.aoci_net, afs_convexity)


def test_loss_avoided_and_carry_given_up_reconcile_to_hedged_minus_unhedged(grid, strategies, scenarios):
    for sc in scenarios:
        base = cell(grid, "unhedged", sc.id)
        assert base.swap_pnl == 0.0 and base.carry_given_up == 0.0
        for st in strategies:
            c = cell(grid, st, sc.id)
            assert c.loss_avoided == c.swap_pnl
            assert c.net_delta_mv - base.net_delta_mv == pytest.approx(c.loss_avoided, abs=1e-9)
            assert c.aoci_net - base.aoci_net == pytest.approx(c.loss_avoided, abs=1e-9)
            assert base.net_carry - c.net_carry == pytest.approx(c.carry_given_up, abs=1e-9)


def test_swap_spread_sensitivity_of_hedge_carry(pv, ctx):
    """How hedge carry moves if the swap spread is +/-25 bp (PLAN.md section 7).

    The spread shifts both the fixed rate (K) and the 3-month floating rate by
    about the same amount, so carry given up changes far less than
    notional x 25 bp: the two legs largely offset. Checked: K and the float
    rate each move by 25 bp +/- 10%, and carry given up moves by under 5% of
    notional x 25 bp.
    """
    full = {s: build_strategies(pv, ctx, swap_spread=s)[2] for s in (-0.0025, 0.0, 0.0025)}
    base_swap = full[0.0].swaps[0]
    for s in (-0.0025, 0.0025):
        swap = full[s].swaps[0]
        assert swap.fixed_rate - base_swap.fixed_rate == pytest.approx(s, rel=0.10)
        assert swap.float_rate_3m(ctx.base) - base_swap.float_rate_3m(ctx.base) == pytest.approx(s, rel=0.10)
        d_carry = swap.carry_12m(ctx.base) - base_swap.carry_12m(ctx.base)
        assert abs(d_carry) < 0.05 * base_swap.notional * 0.0025
