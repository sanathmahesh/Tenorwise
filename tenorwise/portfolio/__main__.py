"""Print the model portfolio summary by sector and class.

    uv run python -m tenorwise.portfolio              # summary
    uv run python -m tenorwise.portfolio --positions  # plus every position
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.fred import FRED_NOTICE
from tenorwise.curve.mortgage_spread import ATTRIBUTION
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.sources import SECTOR_NAMES, load_bny_source
from tenorwise.portfolio.valuation import Aggregate, build_market_context, value_portfolio

HEAD = (f"{'':<26}{'Amort. cost':>12}{'Mkt value':>11}{'Unrealized':>11}{'Weight':>8}"
        f"{'Eff dur':>8}{'Convex.':>8}{'DV01':>8}{'KR DV01 2y/5y/10y/30y ($k/bp)':>34}")


def row(label: str, g: Aggregate) -> str:
    kr = "/".join(f"{1000 * g.key_rate_dv01[b]:.0f}" for b in (2, 5, 10, 30))
    return (f"{label:<26}{g.amortized_cost:>12,.1f}{g.market_value:>11,.1f}{g.unrealized:>11,.1f}"
            f"{100 * g.weight:>7.2f}%{g.eff_duration:>8.2f}{g.convexity:>8.1f}{1000 * g.dv01:>8,.0f}{kr:>34}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.portfolio")
    ap.add_argument("--positions", action="store_true", help="also list every position")
    args = ap.parse_args(argv)

    par = fixture_par_curve()
    mortgage = fixture_mortgage_spread()
    ctx = build_market_context(par, mortgage)
    pv = value_portfolio(load_positions(), ctx)
    cite = load_bny_source()["citation"]

    print(f"Model portfolio. Market data date: {par.data_date}. All amounts in $ millions; DV01 in $ thousands per bp.")
    print(f"Mix based on {cite['company']} Form {cite['form']} for the period ended {cite['period_ended']} "
          f"(filed {cite['filing_date']}), Note 2. Positions are design choices, not BNY's holdings.")
    s = ctx.sector_spreads
    print(f"Sector spreads: Treasuries {1e4 * s['treasuries']:.0f} bp, agency mortgage {1e4 * s['agency_mbs']:.1f} bp "
          f"(calibrated: current-coupon pool at par), agency debt {1e4 * s['agency_debt']:.0f} bp and "
          f"IG corporates proxy {1e4 * s['ig_corporates']:.0f} bp (illustrative).")
    print("Agency mortgage bonds are STYLIZED. IG corporates is a PROXY for BNY's fixed-rate credit holdings "
          "(mainly foreign covered bonds); BNY holds almost no corporate bonds.")
    print()
    print(HEAD)
    print(row("Portfolio", pv.summary))
    print("By sector")
    for sector, g in pv.by_sector.items():
        print(row("  " + SECTOR_NAMES[sector], g))
    print("By class")
    for klass, g in pv.by_class.items():
        print(row("  " + {"AFS": "Available-for-sale (AFS)", "HTM": "Held-to-maturity (HTM)"}[klass], g))
    print()
    print("Average book yield (amortized-cost weighted) against BNY's disclosed yield on amortized cost:")
    for klass, r in pv.book_yields.items():
        print(f"  {klass}: model {100 * r['model']:.3f}%  BNY {100 * r['bny']:.2f}%  gap {r['gap_bp']:+.1f} bp")

    if args.positions:
        print()
        print(f"{'id':<8}{'name':<62}{'Face':>9}{'Book yld':>9}{'Price':>8}{'Mkt value':>10}{'Unreal.':>9}"
              f"{'Eff dur':>8}{'Mod dur*':>9}{'Convex.':>8}{'DV01':>7}")
        for v in pv.positions:
            p = v.position
            print(f"{p.id:<8}{p.name:<62}{p.face:>9,.1f}{100 * p.book_yield:>8.2f}%{v.price:>8.2f}{v.market_value:>10,.1f}"
                  f"{v.unrealized:>9,.1f}{v.eff_duration:>8.2f}{v.mod_duration:>9.2f}{v.convexity:>8.1f}{1000 * v.dv01:>7,.0f}")
        print("* Modified duration is yield-based (the position's own yield); effective duration is curve-based.")
    print()
    print(ATTRIBUTION)
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
