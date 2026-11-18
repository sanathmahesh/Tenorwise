"""Independent benchmark for fixed-rate bonds: the same bonds priced by QuantLib.

Test-only code. QuantLib prices each bond on Tenorwise's own zero curve (same
zero rates, linear interpolation, continuous compounding), so the comparison
checks the bond arithmetic, not the curve. Conventions reduce to Tenorwise's:
  - 30/360 bond basis from a reference date on the 15th, so n months = n/12 years;
  - no calendar, no business-day adjustment, zero settlement lag;
  - semiannual schedule generated backward from maturity, with the previous
    coupon date on or before the reference date (so off-cycle bonds accrue);
  - the sector spread is a continuously compounded addition to the zero rate
    (ZeroSpreadedTermStructure);
  - yield: compounded semiannually; QuantLib's solver accuracy is set to 1e-12.
"""

from __future__ import annotations

import math

import QuantLib as ql

from tenorwise.curve.bootstrap import ZeroCurve
from tenorwise.instruments.bond import FixedRateBond
from tests.benchmark.quantlib_curve import CALENDAR, DAY_COUNT, REFERENCE_DATE

YIELD_ACCURACY = 1e-12

# Tolerances fixed before the first run. Units: price per 100 face; yield as a
# decimal rate; durations in years; convexity in years squared.
TOLERANCES = {
    "dirty_price": (1e-9, "price per 100 face"),
    "clean_price": (1e-9, "price per 100 face"),
    "accrued": (1e-9, "price per 100 face"),
    "yield": (1e-10, "decimal rate"),
    "macaulay_duration": (1e-8, "years"),
    "modified_duration": (1e-8, "years"),
    "convexity": (1e-6, "years squared"),
}


def ql_curve_handle(curve: ZeroCurve) -> ql.YieldTermStructureHandle:
    """Tenorwise's zero curve rebuilt as a QuantLib linear-zero curve."""
    ql.Settings.instance().evaluationDate = REFERENCE_DATE
    dates = [REFERENCE_DATE] + [REFERENCE_DATE + ql.Period(m, ql.Months) for m in curve.tenor_months]
    # Node at t=0 equals the first zero rate: flat short end, as in Tenorwise.
    rates = [curve.zero_rates[0], *curve.zero_rates]
    zc = ql.ZeroCurve(dates, rates, DAY_COUNT, CALENDAR, ql.Linear(), ql.Continuous)
    return ql.YieldTermStructureHandle(zc)


def ql_bond(coupon: float, maturity_months: int) -> ql.FixedRateBond:
    maturity = REFERENCE_DATE + ql.Period(maturity_months, ql.Months)
    periods = math.ceil(maturity_months / 6)
    first_accrual = maturity - ql.Period(6 * periods, ql.Months)
    schedule = ql.Schedule(
        first_accrual,
        maturity,
        ql.Period(ql.Semiannual),
        CALENDAR,
        ql.Unadjusted,
        ql.Unadjusted,
        ql.DateGeneration.Backward,
        False,
    )
    return ql.FixedRateBond(0, 100.0, schedule, [coupon], DAY_COUNT, ql.Unadjusted, 100.0, first_accrual)


def quantlib_measures(
    handle: ql.YieldTermStructureHandle, coupon: float, maturity_months: int, spread: float
) -> dict[str, float]:
    ql.Settings.instance().evaluationDate = REFERENCE_DATE
    spreaded = ql.ZeroSpreadedTermStructure(
        handle, ql.QuoteHandle(ql.SimpleQuote(spread)), ql.Continuous, ql.NoFrequency, DAY_COUNT
    )
    bond = ql_bond(coupon, maturity_months)
    bond.setPricingEngine(ql.DiscountingBondEngine(ql.YieldTermStructureHandle(spreaded)))
    clean = bond.cleanPrice()
    y = ql.BondFunctions.bondYield(
        bond,
        ql.BondPrice(clean, ql.BondPrice.Clean),
        DAY_COUNT,
        ql.Compounded,
        ql.Semiannual,
        REFERENCE_DATE,
        YIELD_ACCURACY,
        100,
    )
    rate = ql.InterestRate(y, DAY_COUNT, ql.Compounded, ql.Semiannual)
    return {
        "dirty_price": bond.dirtyPrice(),
        "clean_price": clean,
        "accrued": bond.accruedAmount(),
        "yield": y,
        "macaulay_duration": ql.BondFunctions.duration(bond, rate, ql.Duration.Macaulay, REFERENCE_DATE),
        "modified_duration": ql.BondFunctions.duration(bond, rate, ql.Duration.Modified, REFERENCE_DATE),
        "convexity": ql.BondFunctions.convexity(bond, rate, REFERENCE_DATE),
    }


def tenorwise_measures(curve: ZeroCurve, coupon: float, maturity_months: int, spread: float) -> dict[str, float]:
    bond = FixedRateBond(coupon=coupon, maturity_months=maturity_months)
    dirty = bond.dirty_price(curve, spread)
    y = bond.yield_from_price(dirty)
    return {
        "dirty_price": dirty,
        "clean_price": bond.clean_price(curve, spread),
        "accrued": bond.accrued_interest(),
        "yield": y,
        "macaulay_duration": bond.macaulay_duration(y),
        "modified_duration": bond.modified_duration(y),
        "convexity": bond.convexity(y),
    }


def bond_differences(curve: ZeroCurve, grid) -> dict[str, list[float]]:
    """Absolute differences per measure across a grid of (coupon, months, spread)."""
    handle = ql_curve_handle(curve)
    out: dict[str, list[float]] = {name: [] for name in TOLERANCES}
    for coupon, months, spread in grid:
        ours = tenorwise_measures(curve, coupon, months, spread)
        theirs = quantlib_measures(handle, coupon, months, spread)
        for name in TOLERANCES:
            out[name].append(abs(ours[name] - theirs[name]))
    return out
