"""Stylized agency mortgage pass-through (PLAN.md section 6).

STYLIZED: the prepayment parameters are illustrative, not calibrated to any
market data, and the valuation is static (no rate volatility, no
option-adjusted spread, no burnout, no seasonality). It exists to show the
two behaviours that make mortgage bonds different from Treasuries:
negative convexity and extension risk.

Plain English: a pool is a bundle of home loans. Each borrower makes a fixed
monthly payment (interest plus some principal), and the investor receives
those payments minus a servicing and guarantee fee. Borrowers can also repay
early ("prepay"), mostly by refinancing when market mortgage rates fall below
their own rate. Prepayment speed is quoted as CPR, the annualised fraction of
the remaining balance repaid early. SMM is the monthly equivalent.

Each month t (1-based) of the projection:
  scheduled payment   = level payment on the remaining balance and term
  gross interest      = balance * WAC / 12
  scheduled principal = scheduled payment - gross interest
  prepayment          = SMM_t * (balance - scheduled principal)
  investor cash flow  = balance * net coupon / 12 + scheduled principal + prepayment
with SMM = 1 - (1 - CPR)^(1/12) and
  CPR = ramp * (CPR_min + (CPR_max - CPR_min) / (1 + exp(-k * (incentive - x0))))
  incentive (percentage points) = WAC - mortgage rate
  mortgage rate = the scenario's 10-year par yield + a fixed mortgage spread
  ramp = min(1, loan age in month t / 30), loan age in month t = age + t.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from tenorwise.curve.bootstrap import ZeroCurve

STYLIZED = True
STYLIZED_NOTE = (
    "Stylized agency pass-through: illustrative prepayment parameters, not calibrated; "
    "static cash flows with no rate volatility, option-adjusted spread, burnout or seasonality."
)
SERVICING_AND_GUARANTEE_FEE = 0.005  # WAC minus net coupon (0.50 percentage point)
TEN_YEAR_MONTHS = 120


def ten_year_par_yield(curve: ZeroCurve) -> float:
    """The (possibly shocked) 10-year par yield the curve was built from, decimal."""
    return curve.par.par_yields[curve.par.tenor_months.index(TEN_YEAR_MONTHS)]


def cpr_to_smm(cpr: float | np.ndarray) -> float | np.ndarray:
    return 1.0 - (1.0 - np.asarray(cpr, dtype=float)) ** (1.0 / 12.0)


def smm_to_cpr(smm: float | np.ndarray) -> float | np.ndarray:
    return 1.0 - (1.0 - np.asarray(smm, dtype=float)) ** 12.0


@dataclass(frozen=True)
class PrepaymentModel:
    """Refinancing-incentive S-curve. STYLIZED: illustrative, not calibrated."""

    cpr_min: float = 0.06
    cpr_max: float = 0.40
    k: float = 3.0  # steepness, per percentage point of incentive
    x0: float = 1.0  # incentive (percentage points) at the midpoint of the S-curve
    ramp_months: int = 30
    stylized_note: str = STYLIZED_NOTE

    def seasoned_cpr(self, incentive_pct: float | np.ndarray) -> float | np.ndarray:
        x = np.asarray(incentive_pct, dtype=float)
        cpr = self.cpr_min + (self.cpr_max - self.cpr_min) / (1.0 + np.exp(-self.k * (x - self.x0)))
        return float(cpr) if np.ndim(incentive_pct) == 0 else cpr

    def ramp(self, age_months: float | np.ndarray) -> float | np.ndarray:
        r = np.minimum(1.0, np.asarray(age_months, dtype=float) / self.ramp_months)
        return float(r) if np.ndim(age_months) == 0 else r

    def cpr(self, incentive_pct: float, age_months: float | np.ndarray) -> float | np.ndarray:
        c = self.ramp(age_months) * self.seasoned_cpr(incentive_pct)
        return float(c) if np.ndim(age_months) == 0 else c


DEFAULT_MODEL = PrepaymentModel()


@dataclass(frozen=True)
class PoolCashFlows:
    months: np.ndarray  # 1..n
    balance_start: np.ndarray
    scheduled_payment: np.ndarray  # borrowers' level payment (gross interest + scheduled principal)
    net_interest: np.ndarray
    scheduled_principal: np.ndarray
    prepayment: np.ndarray
    balance_end: np.ndarray
    cpr: np.ndarray

    @property
    def principal(self) -> np.ndarray:
        return self.scheduled_principal + self.prepayment

    @property
    def total(self) -> np.ndarray:
        """What the investor receives each month."""
        return self.net_interest + self.principal

    @property
    def times(self) -> np.ndarray:
        return self.months / 12.0

    def wal_years(self) -> float:
        """Weighted average life: average time until principal comes back, in years."""
        return float(self.times @ self.principal / self.principal.sum())


@dataclass(frozen=True)
class MortgagePool:
    wac: float  # gross weighted-average coupon of the loans, decimal
    remaining_term_months: int
    age_months: int
    balance: float = 100.0
    fee: float = SERVICING_AND_GUARANTEE_FEE

    def __post_init__(self) -> None:
        if not isinstance(self.remaining_term_months, int) or self.remaining_term_months < 1:
            raise ValueError("remaining_term_months must be a positive whole number")
        if self.age_months < 0:
            raise ValueError("age_months must be non-negative")

    @property
    def net_coupon(self) -> float:
        return self.wac - self.fee

    def incentive_pct(self, mortgage_rate: float) -> float:
        """Refinancing incentive in percentage points: WAC minus the market mortgage rate."""
        return 100.0 * (self.wac - mortgage_rate)

    def cpr_path(self, mortgage_rate: float, model: PrepaymentModel = DEFAULT_MODEL) -> np.ndarray:
        ages = self.age_months + np.arange(1, self.remaining_term_months + 1)
        return np.asarray(model.cpr(self.incentive_pct(mortgage_rate), ages))

    def project(self, cpr_by_month: np.ndarray) -> PoolCashFlows:
        """Monthly investor cash flows for a given CPR in each month."""
        n = self.remaining_term_months
        cpr = np.asarray(cpr_by_month, dtype=float)
        if cpr.shape != (n,):
            raise ValueError(f"need {n} monthly CPRs, got shape {cpr.shape}")
        smm = cpr_to_smm(cpr)
        r = self.wac / 12.0
        out = {name: np.zeros(n) for name in (
            "balance_start", "scheduled_payment", "net_interest", "scheduled_principal", "prepayment", "balance_end"
        )}
        balance = self.balance
        for i in range(n):
            remaining = n - i
            if r > 0:
                payment = balance * r / (1.0 - (1.0 + r) ** (-remaining))
            else:
                payment = balance / remaining
            scheduled = payment - balance * r
            prepay = smm[i] * (balance - scheduled)
            out["balance_start"][i] = balance
            out["scheduled_payment"][i] = payment
            out["net_interest"][i] = balance * self.net_coupon / 12.0
            out["scheduled_principal"][i] = scheduled
            out["prepayment"][i] = prepay
            balance = balance - scheduled - prepay
            out["balance_end"][i] = balance
        return PoolCashFlows(months=np.arange(1, n + 1, dtype=float), cpr=cpr, **out)

    def cash_flows(
        self, curve: ZeroCurve, mortgage_spread: float, model: PrepaymentModel = DEFAULT_MODEL
    ) -> PoolCashFlows:
        """Project once under the curve's scenario: the mortgage rate is its 10y par yield + spread."""
        mortgage_rate = ten_year_par_yield(curve) + mortgage_spread
        return self.project(self.cpr_path(mortgage_rate, model))

    def price(
        self,
        curve: ZeroCurve,
        mortgage_spread: float,
        spread: float = 0.0,
        model: PrepaymentModel = DEFAULT_MODEL,
    ) -> float:
        """Value of the projected cash flows, discounted at exp(-(z(t) + spread) * t).

        Static valuation: the pool is assumed to be priced on a payment date, so
        there is no accrued interest. Units: same as `balance` (100 = per 100).
        """
        cf = self.cash_flows(curve, mortgage_spread, model)
        t = cf.times
        discount = np.exp(-(np.asarray(curve.zero_rate(t)) + spread) * t)
        return float(cf.total @ discount)


def discount_spread_for_price(
    pool: MortgagePool,
    curve: ZeroCurve,
    mortgage_spread: float,
    target_price: float = 100.0,
    model: PrepaymentModel = DEFAULT_MODEL,
) -> float:
    """The constant discount spread (decimal) at which the pool prices to `target_price`.

    Used to define a current-coupon pool: one that trades at par (D-032).
    """
    return brentq(
        lambda s: pool.price(curve, mortgage_spread, s, model) - target_price,
        -0.05,
        0.20,
        xtol=1e-15,
        maxiter=200,
    )

