"""Price a fixed-rate bond on the Treasury curve and print its risk measures.

    uv run python -m tenorwise.analytics --coupon 4.5 --maturity-months 123
    uv run python -m tenorwise.analytics --coupon 5 --maturity-months 120 --spread-bp 100 --face 1000000
    uv run --env-file .env python -m tenorwise.analytics --coupon 4.5 --maturity-months 60 --live
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.analytics.risk import (
    DV01_BUMP_BP,
    EFFECTIVE_BUMP_BP,
    KEY_RATE_BUCKETS,
    KEY_RATE_BUMP_BP,
    build_risk_curves,
    risk_measures,
)
from tenorwise.curve.fred import FRED_NOTICE
from tenorwise.curve.source import load_par_curve
from tenorwise.instruments.bond import FixedRateBond


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.analytics", description=__doc__.split("\n")[0])
    ap.add_argument("--coupon", type=float, required=True, help="annual coupon in percent, e.g. 4.5")
    ap.add_argument("--maturity-months", type=int, required=True, help="remaining whole months, e.g. 123")
    ap.add_argument("--spread-bp", type=float, default=0.0, help="sector spread over Treasuries in bp (default 0)")
    ap.add_argument("--face", type=float, default=100.0, help="face amount in dollars (default 100)")
    ap.add_argument("--live", action="store_true", help="fetch today's curve from FRED instead of the fixture")
    args = ap.parse_args(argv)

    par, source = load_par_curve(args.live)
    curves = build_risk_curves(par)
    bond = FixedRateBond(coupon=args.coupon / 100.0, maturity_months=args.maturity_months, face=args.face)
    spread = args.spread_bp * 1e-4
    r = risk_measures(lambda c: bond.dirty_price(c, spread), curves)
    y = bond.yield_from_price(r.price)
    formula_dv01 = bond.modified_duration(y) * r.price * 1e-4

    years, months = divmod(args.maturity_months, 12)
    print(
        f"Bond: {args.coupon:g}% semiannual coupon, {years}y {months}m to maturity, "
        f"face ${args.face:,.2f}, spread {args.spread_bp:g} bp"
    )
    print(f"Market data date: {par.data_date}  |  Source: {source}")
    if curves.floor_bound:
        print("WARNING: a risk bump hit the 0% floor; curve-based measures are distorted")
    print()
    rows = [
        ("Dirty price", f"${r.price:,.6f}"),
        ("Accrued interest", f"${bond.accrued_interest():,.6f}"),
        ("Clean price", f"${bond.clean_price(curves.base, spread):,.6f}"),
        ("Yield (semiannual)", f"{100 * y:.6f}%"),
        ("", ""),
        ("From the bond's own yield:", ""),
        ("  Macaulay duration", f"{bond.macaulay_duration(y):.6f} years"),
        ("  Modified duration", f"{bond.modified_duration(y):.6f} years"),
        ("  Convexity", f"{bond.convexity(y):.6f}"),
        ("  Formula DV01", f"${formula_dv01:,.6f} per bp (modified duration x price x 0.0001)"),
        ("", ""),
        ("From bumping the curve (par yields moved, curve rebuilt):", ""),
        (f"  Effective duration (+/-{EFFECTIVE_BUMP_BP:g} bp)", f"{r.eff_duration:.6f} years"),
        (f"  Effective convexity (+/-{EFFECTIVE_BUMP_BP:g} bp)", f"{r.eff_convexity:.6f}"),
        (f"  DV01 (+/-{DV01_BUMP_BP:g} bp)", f"${r.dv01:,.6f} per bp"),
    ]
    for label, value in rows:
        print(f"{label:<44}{value}")
    print()
    print(f"Key-rate risk (+/-{KEY_RATE_BUMP_BP:g} bp on each tent):")
    print(f"  {'Bucket':>6} {'KR DV01 $/bp':>16} {'KR duration':>12}")
    for bucket in KEY_RATE_BUCKETS:
        print(f"  {str(bucket) + 'y':>6} {r.key_rate_dv01[bucket]:>16,.6f} {r.key_rate_duration[bucket]:>12.6f}")
    total_krd = sum(r.key_rate_duration.values())
    print(f"  {'Sum':>6} {sum(r.key_rate_dv01.values()):>16,.6f} {total_krd:>12.6f}"
          f"   (effective duration {r.eff_duration:.6f})")
    print()
    print("Positive duration and DV01 mean the bond loses value when rates rise.")
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
