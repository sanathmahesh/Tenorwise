"""Bootstrap a zero curve from Treasury par yields (PLAN.md section 6, Curve).

Plain English: a par yield is the coupon rate at which a bond would trade at
exactly 100. From the 11 par yields we work out a zero rate for each tenor:
the single rate that discounts one dollar paid at that date back to today.

Conventions (all simplifying assumptions; see ASSUMPTIONS.md):
  - time is in years, t = months / 12; no day counts, holidays or settlement lag;
  - rates are decimals here (0.04 = 4%); the API converts to percent;
  - par yields are semiannual bond-equivalent yields;
  - tenors of 6 months and under are one payment with simple interest:
        DF(T) = 1 / (1 + y*T);
  - longer tenors are par bonds paying y/2 every six months. Working outward,
    solve (scipy brentq) for the continuously compounded zero rate at that
    tenor so the bond prices to exactly 100, with zero rates on a straight
    line in time between curve points;
  - interpolation is linear in zero rate, flat beyond the ends, and
        DF(t) = exp(-z(t) * t).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.optimize import brentq

SHORT_END_MAX_MONTHS = 6
ZERO_RATE_BRACKET = (-0.5, 1.0)  # search range for a zero rate, decimal
ZERO_RATE_XTOL = 1e-15


@dataclass(frozen=True)
class ParCurve:
    """Par yields (decimal, semiannual bond-equivalent) at whole-month tenors."""

    data_date: date | None
    tenor_months: tuple[int, ...]
    par_yields: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.tenor_months) != len(self.par_yields):
            raise ValueError("tenor_months and par_yields differ in length")
        if any(m <= 0 for m in self.tenor_months) or list(self.tenor_months) != sorted(
            set(self.tenor_months)
        ):
            raise ValueError("tenor_months must be positive and strictly increasing")

    @property
    def tenors(self) -> np.ndarray:
        return np.array(self.tenor_months, dtype=float) / 12.0


@dataclass(frozen=True)
class ZeroCurve:
    """Continuously compounded zero rates at the par tenors, plus the inputs."""

    par: ParCurve
    zero_rates: tuple[float, ...]

    @property
    def data_date(self) -> date | None:
        return self.par.data_date

    @property
    def tenor_months(self) -> tuple[int, ...]:
        return self.par.tenor_months

    @property
    def tenors(self) -> np.ndarray:
        return self.par.tenors

    def zero_rate(self, t: float | np.ndarray) -> float | np.ndarray:
        """Linear between curve points, flat beyond the ends (numpy.interp does both)."""
        z = np.interp(t, self.tenors, self.zero_rates)
        return float(z) if np.ndim(t) == 0 else z

    def discount_factor(self, t: float | np.ndarray) -> float | np.ndarray:
        t_arr = np.asarray(t, dtype=float)
        df = np.exp(-np.interp(t_arr, self.tenors, self.zero_rates) * t_arr)
        return float(df) if np.ndim(t) == 0 else df


def semiannual_payment_months(maturity_months: int) -> list[int]:
    """Payment times of a semiannual bond, in months: T, T-6, ... while positive."""
    return list(range(maturity_months, 0, -6))[::-1]


def bootstrap(par: ParCurve) -> ZeroCurve:
    known_t: list[float] = []
    known_z: list[float] = []
    for months, y in zip(par.tenor_months, par.par_yields):
        maturity = months / 12.0
        if months <= SHORT_END_MAX_MONTHS:
            # DF = 1 / (1 + y*T)  =>  z = -ln(DF) / T = ln(1 + y*T) / T
            z = math.log1p(y * maturity) / maturity
        else:
            z = _solve_par_bond_zero(known_t, known_z, months, y)
        known_t.append(maturity)
        known_z.append(z)
    return ZeroCurve(par=par, zero_rates=tuple(known_z))


def _solve_par_bond_zero(known_t: list[float], known_z: list[float], months: int, y: float) -> float:
    times = np.array(semiannual_payment_months(months), dtype=float) / 12.0
    maturity = months / 12.0
    coupon = y / 2.0

    def price_minus_par(z_new: float) -> float:
        zs = np.interp(times, known_t + [maturity], known_z + [z_new])
        dfs = np.exp(-zs * times)
        return coupon * dfs.sum() + dfs[-1] - 1.0

    return brentq(price_minus_par, *ZERO_RATE_BRACKET, xtol=ZERO_RATE_XTOL, maxiter=200)


def par_instrument_price(curve: ZeroCurve, months: int, y: float) -> float:
    """Price per 100 face of the curve's own input instrument at this tenor."""
    maturity = months / 12.0
    if months <= SHORT_END_MAX_MONTHS:
        return 100.0 * (1.0 + y * maturity) * curve.discount_factor(maturity)
    times = np.array(semiannual_payment_months(months), dtype=float) / 12.0
    dfs = curve.discount_factor(times)
    return 100.0 * ((y / 2.0) * float(dfs.sum()) + float(dfs[-1]))
