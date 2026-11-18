"""Independent benchmark: the same bootstrap built with QuantLib.

Test-only code (QuantLib is a dev dependency and never ships). Conventions are
chosen so QuantLib's arithmetic reduces to Tenorwise's:
  - day count 30/360 (bond basis) from a reference date on the 15th of a
    month, so the year fraction for n months is exactly n/12;
  - no calendar (NullCalendar), no business-day adjustment, zero settlement lag;
  - tenors of 6 months and under are deposits: DF = 1/(1 + y*T), simple interest;
  - longer tenors are par bonds paying y/2 every six months, priced at 100;
  - PiecewiseLinearZero: continuously compounded zero rates, linear in time.
"""

import QuantLib as ql

from tenorwise.curve.bootstrap import ParCurve

REFERENCE_DATE = ql.Date(15, ql.January, 2026)  # any 15th works; it only anchors the dates
DAY_COUNT = ql.Thirty360(ql.Thirty360.BondBasis)
CALENDAR = ql.NullCalendar()


def quantlib_zero_rates(par: ParCurve) -> list[float]:
    """Continuously compounded zero rates at each par tenor, from QuantLib."""
    ql.Settings.instance().evaluationDate = REFERENCE_DATE
    helpers = []
    for months, y in zip(par.tenor_months, par.par_yields):
        if months <= 6:
            helpers.append(
                ql.DepositRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(y)),
                    ql.Period(months, ql.Months),
                    0,  # fixing days
                    CALENDAR,
                    ql.Unadjusted,
                    False,  # end of month
                    DAY_COUNT,
                )
            )
        else:
            maturity = REFERENCE_DATE + ql.Period(months, ql.Months)
            schedule = ql.Schedule(
                REFERENCE_DATE,
                maturity,
                ql.Period(ql.Semiannual),
                CALENDAR,
                ql.Unadjusted,
                ql.Unadjusted,
                ql.DateGeneration.Backward,
                False,
            )
            helpers.append(
                ql.FixedRateBondHelper(
                    ql.QuoteHandle(ql.SimpleQuote(100.0)),
                    0,  # settlement days
                    100.0,  # face
                    schedule,
                    [y],
                    DAY_COUNT,
                    ql.Unadjusted,
                    100.0,  # redemption
                    REFERENCE_DATE,  # issue date: no accrued interest
                )
            )
    curve = ql.PiecewiseLinearZero(REFERENCE_DATE, helpers, DAY_COUNT)
    out = []
    for months in par.tenor_months:
        d = REFERENCE_DATE + ql.Period(months, ql.Months)
        out.append(curve.zeroRate(d, DAY_COUNT, ql.Continuous).rate())
    return out


def year_fraction(months: int) -> float:
    """QuantLib's year fraction for `months` from the reference date (should be months/12)."""
    return DAY_COUNT.yearFraction(REFERENCE_DATE, REFERENCE_DATE + ql.Period(months, ql.Months))
