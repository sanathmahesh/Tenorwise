"""Pay-fixed interest rate swap (PLAN.md section 7).

Plain English: in a pay-fixed swap the bank pays a fixed rate on a notional
amount and receives a floating rate that resets with the market. If rates
rise, the floating payments it receives go up while its fixed payments don't,
so the swap gains value. That gain offsets losses on fixed-rate bonds: the
swap is the hedge. No notional changes hands.

Swap curve = Treasury zero curve + a flat spread s (default 0; no free SOFR
swap curve is available), so DF_swap(t) = exp(-(z(t) + s) * t). Fixed leg
semiannual at t_i = 0.5, 1.0, ..., T. Per unit notional:
    annuity A        = 0.5 * sum DF(t_i)
    par rate K       = (1 - DF(T)) / A
    value (payer)    = (1 - DF(T)) - K * A        (floating leg worth 1 - DF(T))
    12-month carry   = notional * (3-month floating rate - K), the floating
                       rate implied by the swap curve, held constant
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tenorwise.curve.bootstrap import ZeroCurve, semiannual_payment_months

FLOAT_TENOR_YEARS = 0.25


def _swap_df(curve: ZeroCurve, t: float | np.ndarray, spread: float) -> float | np.ndarray:
    t_arr = np.asarray(t, dtype=float)
    df = np.exp(-(np.asarray(curve.zero_rate(t_arr)) + spread) * t_arr)
    return float(df) if np.ndim(t) == 0 else df


def annuity(curve: ZeroCurve, tenor_months: int, spread: float = 0.0) -> float:
    times = np.array(semiannual_payment_months(tenor_months), dtype=float) / 12.0
    return float(0.5 * np.sum(_swap_df(curve, times, spread)))


def par_swap_rate(curve: ZeroCurve, tenor_months: int, spread: float = 0.0) -> float:
    return (1.0 - _swap_df(curve, tenor_months / 12.0, spread)) / annuity(curve, tenor_months, spread)


def float_rate_3m(curve: ZeroCurve, spread: float = 0.0) -> float:
    """Simple-interest 3-month rate on the swap curve: (1/DF(0.25) - 1) / 0.25."""
    return (1.0 / _swap_df(curve, FLOAT_TENOR_YEARS, spread) - 1.0) / FLOAT_TENOR_YEARS


@dataclass(frozen=True)
class PayFixedSwap:
    tenor_months: int
    notional: float  # $M
    fixed_rate: float  # decimal
    swap_spread: float = 0.0

    @classmethod
    def at_par(cls, curve: ZeroCurve, tenor_months: int, notional: float, swap_spread: float = 0.0) -> PayFixedSwap:
        """Enter the swap at today's par rate, so it is worth zero at inception."""
        return cls(tenor_months, notional, par_swap_rate(curve, tenor_months, swap_spread), swap_spread)

    @property
    def tenor_years(self) -> float:
        return self.tenor_months / 12.0

    def value(self, curve: ZeroCurve) -> float:
        """Value to the fixed payer on the (possibly shocked) curve, in notional units."""
        floating = 1.0 - _swap_df(curve, self.tenor_years, self.swap_spread)
        fixed = self.fixed_rate * annuity(curve, self.tenor_months, self.swap_spread)
        return self.notional * (floating - fixed)

    def float_rate_3m(self, curve: ZeroCurve) -> float:
        return float_rate_3m(curve, self.swap_spread)

    def carry_12m(self, curve: ZeroCurve) -> float:
        """Net interest over 12 months: receive the floating rate, pay the fixed rate."""
        return self.notional * (self.float_rate_3m(curve) - self.fixed_rate)
