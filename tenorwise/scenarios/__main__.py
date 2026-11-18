"""Print the seven-scenario table for the model portfolio.

    uv run python -m tenorwise.scenarios               # totals
    uv run python -m tenorwise.scenarios --by-sector   # plus change in value by sector
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.fred import FRED_NOTICE
from tenorwise.curve.mortgage_spread import ATTRIBUTION
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.sources import SECTOR_NAMES
from tenorwise.portfolio.valuation import build_market_context
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.replay import load_replay_fixture, replay_shock_bp
from tenorwise.scenarios.revaluation import run_scenario


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.scenarios")
    ap.add_argument("--by-sector", action="store_true", help="also show change in value by sector")
    args = ap.parse_args(argv)

    par = fixture_par_curve()
    ctx = build_market_context(par, fixture_mortgage_spread())
    positions = load_positions()
    scenarios = preset_scenarios(replay_shock_bp(*load_replay_fixture().parsed()))
    base = run_scenario(Scenario("base", "No shock", "", (0.0,) * len(par.tenor_months)), positions, ctx)
    results = [run_scenario(s, positions, ctx) for s in scenarios]

    print(f"Seven-scenario table. Market data date: {par.data_date}. $ millions, pre-tax. "
          f"Instantaneous shocks to Treasury par yields; spreads held fixed.")
    print(f"Base: market value {base.total.base_mv:,.1f}; 12-month carry {base.total.carry_12m:,.1f}.")
    print()
    idx = {m: i for i, m in enumerate(par.tenor_months)}
    print(f"{'Scenario':<20}{'2y/10y/30y bp':>16}{'Change in MV':>14}{'%':>8}{'AOCI (AFS)':>12}"
          f"{'HTM, not rec.':>15}{'12m carry':>11}{'vs base':>9}")
    for r in results:
        sh = r.scenario.shock_bp
        shocks = "/".join(f"{sh[idx[m]]:+.0f}" for m in (24, 120, 360))
        print(f"{r.scenario.name:<20}{shocks:>16}{r.total.delta_mv:>14,.1f}{100 * r.total.delta_mv_pct:>7.2f}%"
              f"{r.total.aoci_impact:>12,.1f}{r.total.htm_unrecognized:>15,.1f}{r.total.carry_12m:>11,.1f}"
              f"{r.total.carry_12m - base.total.carry_12m:>+9.1f}" + ("  FLOOR" if r.floor_bound else ""))
    if args.by_sector:
        print()
        print("Change in market value by sector ($M):")
        print(f"{'Scenario':<20}" + "".join(f"{SECTOR_NAMES[s][:22]:>24}" for s in SECTOR_NAMES))
        for r in results:
            print(f"{r.scenario.name:<20}" + "".join(f"{r.by_sector[s].delta_mv:>24,.1f}" for s in SECTOR_NAMES))
    print()
    print("AOCI impact: change in available-for-sale value, which flows into equity. HTM change: real, but not")
    print("recognized in the accounts (held-to-maturity is carried at amortized cost). Carry: gross interest")
    print("income over 12 months, no funding cost. Agency mortgage bonds are STYLIZED.")
    print(ATTRIBUTION)
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
