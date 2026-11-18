"""Print the Treasury curve and its data date.

    uv run python -m tenorwise.curve                      # pinned fixture (offline)
    uv run --env-file .env python -m tenorwise.curve --live
    uv run python -m tenorwise.curve --parallel 100       # +100 bp parallel shock
    uv run python -m tenorwise.curve --key-rate 10 25     # +25 bp at the 10-year tent
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fred import FRED_NOTICE, PAR_SERIES
from tenorwise.curve.shocks import KEY_RATE_BUCKETS, apply_shock, key_rate_shock, parallel_shock
from tenorwise.curve.source import load_par_curve


def tenor_label(months: int) -> str:
    return f"{months}M" if months < 12 else f"{months // 12}Y"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.curve", description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true", help="fetch from FRED now instead of the pinned fixture")
    ap.add_argument("--parallel", type=float, metavar="BP", help="parallel shock in basis points")
    ap.add_argument(
        "--key-rate", nargs=2, type=float, action="append", metavar=("BUCKET", "BP"),
        help=f"key-rate shock; BUCKET is one of {KEY_RATE_BUCKETS}; may repeat",
    )
    args = ap.parse_args(argv)

    par, source = load_par_curve(args.live)
    shock = parallel_shock(0.0)
    labels = []
    if args.parallel:
        shock = shock + parallel_shock(args.parallel)
        labels.append(f"parallel {args.parallel:+g} bp")
    for bucket, bp in args.key_rate or []:
        shock = shock + key_rate_shock(int(bucket), bp)
        labels.append(f"{int(bucket)}y key rate {bp:+g} bp")

    base = bootstrap(par)
    shocked = apply_shock(par, shock)
    curve = shocked.curve

    print(f"US Treasury curve. Market data date: {par.data_date}")
    print(f"Source: {source}")
    print(f"Shock: {', '.join(labels) if labels else 'none'}")
    if shocked.floor_bound:
        floored = ", ".join(tenor_label(m) for m in shocked.floored_tenor_months)
        print(f"ZERO FLOOR BINDS: shocked par yields floored at 0% at {floored}")
    print()
    head = f"{'Tenor':>5} {'FRED series':>11} {'Par yield %':>12} {'Zero rate %':>12} {'Discount factor':>16}"
    if labels:
        head += f" {'Shock bp':>9} {'Zero chg bp':>12}"
    print(head)
    for i, (sid, months) in enumerate(PAR_SERIES):
        row = (
            f"{tenor_label(months):>5} {sid:>11} {100 * curve.par.par_yields[i]:>12.4f}"
            f" {100 * curve.zero_rates[i]:>12.4f} {curve.discount_factor(months / 12):>16.10f}"
        )
        if labels:
            dz = 1e4 * (curve.zero_rates[i] - base.zero_rates[i])
            row += f" {shocked.shock_bp[i]:>9.2f} {dz:>12.2f}"
        print(row)
    print()
    print("Par yields: semiannual bond-equivalent. Zero rates: continuously compounded.")
    print("Interpolation: linear in zero rate between points, flat beyond 1M and 30Y.")
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
