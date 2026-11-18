"""Yield-based measures for a stream of fixed cash flows.

Plain English: a bond's yield is the one interest rate that, applied to every
cash flow, reproduces its price. Duration and convexity computed from that
yield describe how the price responds if that single rate moves.

Conventions: times in years (months / 12); the yield is compounded
semiannually, so a cash flow at time t is discounted by (1 + y/2)^(-2t),
including fractional periods for off-cycle cash flows.
  Macaulay duration  = sum(t * PV) / price                     (years)
  modified duration  = Macaulay / (1 + y/2)                    (years)
  convexity          = sum(CF * t*(t + 0.5) * (1 + y/2)^(-2t-2)) / price
                     = (1/P) d2P/dy2                           (years squared)
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

YIELD_BRACKET = (-0.5, 2.0)  # search range for a yield, decimal
YIELD_XTOL = 1e-15


def price_from_yield(times: np.ndarray, amounts: np.ndarray, y: float) -> float:
    return float(amounts @ (1.0 + y / 2.0) ** (-2.0 * times))


def yield_from_price(times: np.ndarray, amounts: np.ndarray, dirty_price: float) -> float:
    """The semiannually compounded yield that reproduces the dirty price."""
    return brentq(
        lambda y: price_from_yield(times, amounts, y) - dirty_price,
        *YIELD_BRACKET,
        xtol=YIELD_XTOL,
        maxiter=200,
    )


def macaulay_duration(times: np.ndarray, amounts: np.ndarray, y: float) -> float:
    pv = amounts * (1.0 + y / 2.0) ** (-2.0 * times)
    return float(times @ pv / pv.sum())


def modified_duration(times: np.ndarray, amounts: np.ndarray, y: float) -> float:
    return macaulay_duration(times, amounts, y) / (1.0 + y / 2.0)


def convexity(times: np.ndarray, amounts: np.ndarray, y: float) -> float:
    price = price_from_yield(times, amounts, y)
    second = amounts * times * (times + 0.5) * (1.0 + y / 2.0) ** (-2.0 * times - 2.0)
    return float(second.sum() / price)
