"""Independent benchmark for pay-fixed swaps: QuantLib VanillaSwap on the same curve.

Test-only. Conventions reduce to Tenorwise's single-curve formula:
  - 30/360 from a reference date on the 15th (n months = n/12 years), no
    calendar, no adjustment, zero fixing and settlement days;
  - fixed leg semiannual; floating leg quarterly on a 3-month index that
    projects off the same (swap) curve with 30/360 accrual, so the floating
    leg's value telescopes to 1 - DF(T);
  - the swap spread is a continuously compounded addition to the zero rate
    (ZeroSpreadedTermStructure), as in Tenorwise.
"""

from __future__ import annotations

import QuantLib as ql

from tests.benchmark.quantlib_curve import CALENDAR, DAY_COUNT, REFERENCE_DATE

TOLERANCES = {
    "swap_par_rate": (1e-10, "decimal rate"),
    "swap_value": (1e-10, "value per unit notional"),
}


def _spreaded(handle: ql.YieldTermStructureHandle, spread: float) -> ql.YieldTermStructureHandle:
    return ql.YieldTermStructureHandle(
        ql.ZeroSpreadedTermStructure(handle, ql.QuoteHandle(ql.SimpleQuote(spread)), ql.Continuous, ql.NoFrequency, DAY_COUNT)
    )


def quantlib_swap(
    handle: ql.YieldTermStructureHandle, tenor_months: int, fixed_rate: float, spread: float = 0.0
) -> tuple[float, float]:
    """(fair fixed rate, NPV per unit notional to the fixed payer)."""
    ql.Settings.instance().evaluationDate = REFERENCE_DATE
    curve = _spreaded(handle, spread)
    index = ql.IborIndex("TW3M", ql.Period(3, ql.Months), 0, ql.USDCurrency(), CALENDAR, ql.Unadjusted, False, DAY_COUNT, curve)
    maturity = REFERENCE_DATE + ql.Period(tenor_months, ql.Months)
    fixed = ql.Schedule(REFERENCE_DATE, maturity, ql.Period(ql.Semiannual), CALENDAR, ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Forward, False)
    floating = ql.Schedule(REFERENCE_DATE, maturity, ql.Period(ql.Quarterly), CALENDAR, ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Forward, False)
    swap = ql.VanillaSwap(ql.VanillaSwap.Payer, 1.0, fixed, fixed_rate, DAY_COUNT, floating, index, 0.0, DAY_COUNT)
    swap.setPricingEngine(ql.DiscountingSwapEngine(curve))
    return swap.fairRate(), swap.NPV()
