"""Fixed-rate bullet bond (PLAN.md section 6, Fixed-rate bonds).

Plain English: the bond pays half its annual coupon every six months and
returns its face value at maturity. Its value today is each payment
discounted at the curve's zero rate for that date, plus a constant spread for
the bond's sector (extra yield investors demand over Treasuries).

  dirty price = sum( CF * exp(-(z(t) + s) * t) )
  accrued     = semiannual coupon * fraction of the current half-year elapsed
  clean price = dirty - accrued

Conventions: cash flows at T, T-0.5, ... while positive (so an off-cycle bond
has a short time to its next coupon); whole months; no call features and no
floating rates. Prices are in the same units as `face` (100 = per 100 face).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tenorwise.analytics import yield_measures as ym
from tenorwise.curve.bootstrap import ZeroCurve, semiannual_payment_months


@dataclass(frozen=True)
class FixedRateBond:
    coupon: float  # annual coupon rate, decimal (0.045 = 4.5%)
    maturity_months: int  # remaining whole months to maturity
    face: float = 100.0

    def __post_init__(self) -> None:
        if not isinstance(self.maturity_months, int) or self.maturity_months < 1:
            raise ValueError("maturity_months must be a positive whole number")
        if self.face <= 0:
            raise ValueError("face must be positive")

    # ------------------------------------------------------------ cash flows

    def payment_months(self) -> list[int]:
        return semiannual_payment_months(self.maturity_months)

    def cash_flows(self) -> tuple[np.ndarray, np.ndarray]:
        """(times in years, amounts) of every remaining payment."""
        months = np.array(self.payment_months(), dtype=float)
        amounts = np.full(months.shape, self.face * self.coupon / 2.0)
        amounts[-1] += self.face
        return months / 12.0, amounts

    def accrued_interest(self) -> float:
        months_to_next = self.payment_months()[0]  # 1..6
        elapsed = 6 - months_to_next
        return self.face * (self.coupon / 2.0) * elapsed / 6.0

    # ------------------------------------------------------------ curve pricing

    def dirty_price(self, curve: ZeroCurve, spread: float = 0.0) -> float:
        times, amounts = self.cash_flows()
        discount = np.exp(-(np.asarray(curve.zero_rate(times)) + spread) * times)
        return float(amounts @ discount)

    def clean_price(self, curve: ZeroCurve, spread: float = 0.0) -> float:
        return self.dirty_price(curve, spread) - self.accrued_interest()

    # ------------------------------------------------------------ yield-based

    def price_from_yield(self, y: float) -> float:
        return ym.price_from_yield(*self.cash_flows(), y)

    def yield_from_price(self, dirty_price: float) -> float:
        return ym.yield_from_price(*self.cash_flows(), dirty_price)

    def macaulay_duration(self, y: float) -> float:
        return ym.macaulay_duration(*self.cash_flows(), y)

    def modified_duration(self, y: float) -> float:
        return ym.modified_duration(*self.cash_flows(), y)

    def convexity(self, y: float) -> float:
        return ym.convexity(*self.cash_flows(), y)
