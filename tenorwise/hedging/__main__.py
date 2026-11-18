"""Print the hedge strategies and the strategy-by-scenario matrix.

    uv run python -m tenorwise.hedging
    uv run python -m tenorwise.hedging --swap-spread-bp 25
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.fred import FRED_NOTICE
from tenorwise.curve.mortgage_spread import ATTRIBUTION
from tenorwise.hedging.grid import run_grid
from tenorwise.hedging.strategies import afs_risk, build_strategies
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context, value_portfolio
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.replay import load_replay_fixture, replay_shock_bp


def k(x: float) -> str:
    """$M -> whole $ thousands, without a negative zero."""
    return f"{round(1000 * x) + 0:,}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.hedging")
    ap.add_argument("--swap-spread-bp", type=float, default=0.0, help="swap curve = Treasury zero curve + this spread (default 0)")
    args = ap.parse_args(argv)

    par = fixture_par_curve()
    ctx = build_market_context(par, fixture_mortgage_spread())
    positions = load_positions()
    pv = value_portfolio(positions, ctx)
    afs = afs_risk(pv)
    strategies = build_strategies(pv, ctx, swap_spread=args.swap_spread_bp * 1e-4)
    no_shock = Scenario("no_shock", "No shock", "Today's curve.", (0.0,) * len(par.tenor_months))
    scenarios = [no_shock] + preset_scenarios(replay_shock_bp(*load_replay_fixture().parsed()))
    grid = run_grid(strategies, scenarios, positions, ctx)
    cell = {(c.strategy_id, c.scenario_id): c for c in grid}

    print(f"Hedging the AFS book with pay-fixed swaps. Market data date: {par.data_date}. $ millions; DV01 in $ thousands per bp.")
    print(f"Swap curve = Treasury zero curve + {args.swap_spread_bp:g} bp (assumption: no free SOFR swap curve). "
          "Swaps sized once on today's curve, never rebalanced; treated as perfectly effective fair-value hedges.")
    print(f"AFS book: market value {afs.market_value:,.1f}, DV01 {1000 * afs.dv01:,.0f}, key-rate DV01 2y/5y/10y/30y "
          + "/".join(f"{1000 * afs.key_rate_dv01[b]:.0f}" for b in (2, 5, 10, 30)) + ".")
    print()
    print(f"{'Strategy':<24}{'Swaps (tenor: notional @ fixed rate, DV01)':<62}{'DV01 after':>11}{'KR DV01 after 2y/5y/10y/30y':>30}")
    for st in strategies:
        swaps = "; ".join(f"{s.tenor_months // 12}y: {s.notional:,.0f} @ {100 * s.fixed_rate:.3f}%, {k(d)}"
                          for s, d in zip(st.swaps, st.swap_dv01)) or "none"
        kr = "/".join(k(st.key_rate_dv01_after[b]) for b in (2, 5, 10, 30))
        print(f"{st.name:<24}{swaps:<62}{k(st.dv01_after):>11}{kr:>30}")

    print()
    print("AOCI net of hedges (AFS change + swap gain or loss), pre-tax:")
    print(f"{'Scenario':<20}" + "".join(f"{st.name:>24}" for st in strategies))
    for sc in scenarios:
        print(f"{sc.name:<20}" + "".join(f"{cell[(st.id, sc.id)].aoci_net:>24,.1f}" for st in strategies))
    print()
    print("Loss avoided (swap gain) / carry given up over 12 months:")
    print(f"{'Scenario':<20}" + "".join(f"{st.name:>24}" for st in strategies[1:]))
    for sc in scenarios:
        print(f"{sc.name:<20}" + "".join(
            f"{cell[(st.id, sc.id)].loss_avoided:>14,.1f} / {cell[(st.id, sc.id)].carry_given_up:>6,.1f}" for st in strategies[1:]))
    base_carry = cell[("unhedged", scenarios[0].id)].net_carry
    print()
    print(f"Unhedged 12-month carry: {base_carry:,.1f}. Carry given up = fixed rate paid minus 3-month floating rate received, on the notional.")
    print("Agency mortgage bonds are STYLIZED. Hedging covers AFS only: HTM interest-rate risk cannot be a hedged risk under ASC 815-20-25-43.")
    print(ATTRIBUTION)
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
