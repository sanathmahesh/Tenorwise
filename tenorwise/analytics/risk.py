"""Curve-based risk by bump-and-reprice (PLAN.md section 6).

Plain English: shift the yield curve a little, reprice, and see how much the
value changes.

  effective duration  = (P(-25bp) - P(+25bp)) / (2 * P0 * 0.0025)
      roughly "% value lost per 1 percentage point rise in rates"
  effective convexity = (P(-25bp) + P(+25bp) - 2*P0) / (P0 * 0.0025^2)
      how much that sensitivity itself changes as rates move
  DV01                = (P(-1bp) - P(+1bp)) / 2
      dollars lost per 1 bp rise in rates
  key-rate DV01 (k)   = the same, bumping only the tent at k = 2, 5, 10 or 30 years
  key-rate duration   = key-rate DV01 / (P0 * 0.0001)

Sign convention: duration and DV01 are positive for an ordinary long bond,
which loses value when rates rise.

Every bump goes through tenorwise.curve.shocks.apply_shock (par yields moved,
curve rebuilt). The 12 bumped curves are built once per base curve and every
instrument is repriced on them; the instrument only has to supply
`price(curve) -> value`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tenorwise.curve.bootstrap import ParCurve, ZeroCurve, bootstrap
from tenorwise.curve.shocks import BP, KEY_RATE_BUCKETS, apply_shock, key_rate_shock, parallel_shock

EFFECTIVE_BUMP_BP = 25.0
DV01_BUMP_BP = 1.0
KEY_RATE_BUMP_BP = 1.0

__all__ = [
    "DV01_BUMP_BP",
    "EFFECTIVE_BUMP_BP",
    "KEY_RATE_BUCKETS",
    "KEY_RATE_BUMP_BP",
    "RiskCurves",
    "RiskMeasures",
    "build_risk_curves",
    "dollar_convexity",
    "risk_measures",
]


@dataclass(frozen=True)
class RiskCurves:
    base: ZeroCurve
    parallel: Mapping[float, ZeroCurve]  # keyed by shock in bp: +25, -25, +1, -1
    key_rate: Mapping[tuple[int, float], ZeroCurve]  # keyed by (bucket, +1 or -1)
    floor_bound: bool  # True if any bump hit the 0% floor (measures then distorted)


def build_risk_curves(par: ParCurve) -> RiskCurves:
    parallel: dict[float, ZeroCurve] = {}
    key_rate: dict[tuple[int, float], ZeroCurve] = {}
    floor = False
    for bp in (EFFECTIVE_BUMP_BP, -EFFECTIVE_BUMP_BP, DV01_BUMP_BP, -DV01_BUMP_BP):
        shocked = apply_shock(par, parallel_shock(bp, len(par.tenor_months)))
        parallel[bp] = shocked.curve
        floor |= shocked.floor_bound
    for bucket in KEY_RATE_BUCKETS:
        for bp in (KEY_RATE_BUMP_BP, -KEY_RATE_BUMP_BP):
            shocked = apply_shock(par, key_rate_shock(bucket, bp, par.tenor_months))
            key_rate[(bucket, bp)] = shocked.curve
            floor |= shocked.floor_bound
    return RiskCurves(base=bootstrap(par), parallel=parallel, key_rate=key_rate, floor_bound=floor)


@dataclass(frozen=True)
class RiskMeasures:
    price: float
    eff_duration: float | None  # None when the base value is zero (e.g. a swap at par)
    eff_convexity: float | None
    dv01: float
    key_rate_dv01: dict[int, float]
    key_rate_duration: dict[int, float] | None


def risk_measures(price: Callable[[ZeroCurve], float], curves: RiskCurves) -> RiskMeasures:
    p0 = price(curves.base)
    h = EFFECTIVE_BUMP_BP * BP
    up = price(curves.parallel[EFFECTIVE_BUMP_BP])
    down = price(curves.parallel[-EFFECTIVE_BUMP_BP])
    dv01 = (price(curves.parallel[-DV01_BUMP_BP]) - price(curves.parallel[DV01_BUMP_BP])) / (
        2.0 * DV01_BUMP_BP
    )
    kr_dv01 = {
        bucket: (
            price(curves.key_rate[(bucket, -KEY_RATE_BUMP_BP)])
            - price(curves.key_rate[(bucket, KEY_RATE_BUMP_BP)])
        )
        / (2.0 * KEY_RATE_BUMP_BP)
        for bucket in KEY_RATE_BUCKETS
    }
    if p0 == 0.0:
        return RiskMeasures(p0, None, None, dv01, kr_dv01, None)
    return RiskMeasures(
        price=p0,
        eff_duration=(down - up) / (2.0 * p0 * h),
        eff_convexity=(down + up - 2.0 * p0) / (p0 * h * h),
        dv01=dv01,
        key_rate_dv01=kr_dv01,
        key_rate_duration={b: v / (p0 * BP) for b, v in kr_dv01.items()},
    )


def dollar_convexity(price: Callable[[ZeroCurve], float], curves: RiskCurves) -> float:
    """Second difference of value over +/-25 bp parallel bumps, per (decimal rate)^2.

    Unlike effective convexity it is not divided by value, so it adds across
    positions and works for instruments worth zero (a swap at inception).
    A value change of about 0.5 * dollar_convexity * dy^2 comes on top of the
    duration effect.
    """
    h = EFFECTIVE_BUMP_BP * BP
    up = price(curves.parallel[EFFECTIVE_BUMP_BP])
    down = price(curves.parallel[-EFFECTIVE_BUMP_BP])
    return (up + down - 2.0 * price(curves.base)) / (h * h)

