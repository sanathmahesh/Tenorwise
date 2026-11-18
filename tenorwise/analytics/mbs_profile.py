"""How a stylized mortgage pool behaves as rates move, next to a similar Treasury.

    uv run python -m tenorwise.analytics.mbs_profile
    uv run python -m tenorwise.analytics.mbs_profile --wac 6.5 --age 60 --remaining 300

Row fields follow the mbs.json contract (PLAN.md section 8): profile rows have
shift_bp, price, eff_duration, avg_life_years, cpr; the Treasury comparison has
shift_bp, price; the S-curve has incentive_pct, cpr. STYLIZED throughout.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import numpy as np

from tenorwise.analytics.risk import build_risk_curves, risk_measures
from tenorwise.curve.bootstrap import ParCurve, ZeroCurve, bootstrap
from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.fred import FRED_NOTICE
from tenorwise.curve.mortgage_spread import ATTRIBUTION, MortgageSpread
from tenorwise.curve.shocks import apply_shock, parallel_shock
from tenorwise.instruments.bond import FixedRateBond
from tenorwise.instruments.mbs import (
    DEFAULT_MODEL,
    STYLIZED_NOTE,
    MortgagePool,
    PrepaymentModel,
    discount_spread_for_price,
    ten_year_par_yield,
)

DEFAULT_SHIFTS_BP = tuple(range(-300, 301, 50))
S_CURVE_INCENTIVES = tuple(float(x) for x in np.arange(-3.0, 4.0 + 1e-9, 0.25))
DEMO_AGE_MONTHS = 36
DEMO_REMAINING_MONTHS = 324


@dataclass(frozen=True)
class ProfileRow:
    shift_bp: float
    ten_year_par: float  # decimal
    mortgage_rate: float  # decimal
    incentive_pct: float
    cpr: float  # first projected month, decimal
    avg_life_years: float
    price: float
    eff_duration: float
    eff_convexity: float
    floor_bound: bool


def current_coupon_pool(curve: ZeroCurve, mortgage_spread: float) -> MortgagePool:
    """WAC equal to today's mortgage rate, seasoned 36 months (D-032)."""
    return MortgagePool(
        wac=ten_year_par_yield(curve) + mortgage_spread,
        remaining_term_months=DEMO_REMAINING_MONTHS,
        age_months=DEMO_AGE_MONTHS,
    )


def mbs_profile(
    pool: MortgagePool,
    par: ParCurve,
    mortgage_spread: float,
    discount_spread: float,
    shifts_bp: tuple[float, ...] = DEFAULT_SHIFTS_BP,
    model: PrepaymentModel = DEFAULT_MODEL,
) -> list[ProfileRow]:
    rows = []
    for bp in shifts_bp:
        shocked = apply_shock(par, parallel_shock(bp, len(par.tenor_months)))
        curves = build_risk_curves(shocked.curve.par)
        r = risk_measures(lambda c: pool.price(c, mortgage_spread, discount_spread, model), curves)
        cf = pool.cash_flows(curves.base, mortgage_spread, model)
        y10 = ten_year_par_yield(curves.base)
        rows.append(
            ProfileRow(
                shift_bp=float(bp),
                ten_year_par=y10,
                mortgage_rate=y10 + mortgage_spread,
                incentive_pct=pool.incentive_pct(y10 + mortgage_spread),
                cpr=float(cf.cpr[0]),
                avg_life_years=cf.wal_years(),
                price=r.price,
                eff_duration=r.eff_duration,
                eff_convexity=r.eff_convexity,
                floor_bound=shocked.floor_bound or curves.floor_bound,
            )
        )
    return rows


def matching_treasury(par: ParCurve, target_duration: float) -> FixedRateBond:
    """Treasury bullet (coupon = 10y par yield) whose effective duration is closest to the target."""
    curves = build_risk_curves(par)
    coupon = ten_year_par_yield(curves.base)
    candidates = [FixedRateBond(coupon=coupon, maturity_months=m) for m in range(6, 361, 6)]
    return min(
        candidates,
        key=lambda b: abs(risk_measures(b.dirty_price, curves).eff_duration - target_duration),
    )


def treasury_comparison(
    bond: FixedRateBond, par: ParCurve, shifts_bp: tuple[float, ...] = DEFAULT_SHIFTS_BP
) -> list[tuple[float, float]]:
    return [
        (float(bp), bond.dirty_price(apply_shock(par, parallel_shock(bp, len(par.tenor_months))).curve))
        for bp in shifts_bp
    ]


def s_curve(
    model: PrepaymentModel = DEFAULT_MODEL, incentives: tuple[float, ...] = S_CURVE_INCENTIVES
) -> list[tuple[float, float]]:
    return [(x, model.seasoned_cpr(x)) for x in incentives]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.analytics.mbs_profile")
    ap.add_argument("--wac", type=float, help="gross coupon in percent (default: today's mortgage rate)")
    ap.add_argument("--age", type=int, default=DEMO_AGE_MONTHS, help="loan age in months (default 36)")
    ap.add_argument("--remaining", type=int, default=DEMO_REMAINING_MONTHS, help="remaining term in months (default 324)")
    ap.add_argument("--discount-spread-bp", type=float, help="discount spread in bp (default: the spread that prices the pool at par)")
    args = ap.parse_args(argv)

    par = fixture_par_curve()
    base = bootstrap(par)
    ms: MortgageSpread = fixture_mortgage_spread()
    pool = current_coupon_pool(base, ms.spread)
    if args.wac is not None or args.age != DEMO_AGE_MONTHS or args.remaining != DEMO_REMAINING_MONTHS:
        pool = MortgagePool(
            wac=(args.wac / 100.0) if args.wac is not None else pool.wac,
            remaining_term_months=args.remaining,
            age_months=args.age,
        )
    if args.discount_spread_bp is None:
        disc = discount_spread_for_price(pool, base, ms.spread, 100.0)
        disc_label = f"{disc * 1e4:.1f} bp (solved so the base price is 100)"
    else:
        disc = args.discount_spread_bp * 1e-4
        disc_label = f"{args.discount_spread_bp:g} bp (given)"

    print(STYLIZED_NOTE.replace("Stylized", "STYLIZED", 1))
    print(f"Market data date: {par.data_date}. Mortgage spread {100 * ms.spread:.2f} pp on {ms.date} "
          f"({100 * ms.mortgage_rate:.2f}% mortgage rate - {100 * ms.ten_year_yield:.2f}% 10y Treasury).")
    print(f"Pool: WAC {100 * pool.wac:.3f}%, net coupon {100 * pool.net_coupon:.3f}%, age {pool.age_months}m, "
          f"{pool.remaining_term_months}m remaining. Discount spread {disc_label}.")
    m = DEFAULT_MODEL
    print(f"Prepayment S-curve (illustrative, not calibrated): CPR_min {m.cpr_min:.0%}, CPR_max {m.cpr_max:.0%}, "
          f"k {m.k:g}, x0 {m.x0:g} pp, ramp {m.ramp_months} months.")
    print()

    rows = mbs_profile(pool, par, ms.spread, disc)
    base_row = next(r for r in rows if r.shift_bp == 0)
    tsy = matching_treasury(par, base_row.eff_duration)
    tsy_prices = dict(treasury_comparison(tsy, par))
    print(f"{'Shift':>6} {'10y par':>8} {'Mtg rate':>9} {'Incent.':>8} {'CPR':>6} {'Avg life':>9} "
          f"{'Price':>8} {'Eff dur':>8} {'Eff conv':>9} {'Tsy price':>10}")
    for r in rows:
        print(f"{r.shift_bp:>+6.0f} {100 * r.ten_year_par:>7.2f}% {100 * r.mortgage_rate:>8.2f}% "
              f"{r.incentive_pct:>+7.2f} {100 * r.cpr:>5.1f}% {r.avg_life_years:>7.2f} y "
              f"{r.price:>8.3f} {r.eff_duration:>8.2f} {r.eff_convexity:>9.1f} {tsy_prices[r.shift_bp]:>10.3f}"
              + ("  FLOOR" if r.floor_bound else ""))
    years, months = divmod(tsy.maturity_months, 12)
    print()
    print(f"Treasury comparison: {100 * tsy.coupon:.2f}% bullet, {years}y {months}m, effective duration closest to the pool's at base.")
    print("Price per 100 of current balance. Incentive = WAC - mortgage rate, in percentage points.")
    print(ATTRIBUTION)
    print(FRED_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
