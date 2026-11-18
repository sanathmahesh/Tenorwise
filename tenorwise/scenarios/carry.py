"""12-month carry: gross interest income over the next year (PLAN.md section 6).

Plain English: carry is what the portfolio earns just by holding its bonds,
before any change in their market value.

    carry = sum over the next 12 months of (amortized cost at the start of the month * book yield / 12)

  - bullet bonds bought at par: amortized cost stays at face until maturity,
    so carry = amortized cost * book yield * min(12, months left) / 12;
  - mortgage pools bought at par: amortized cost = balance, which runs down
    with scheduled principal and the scenario's prepayments. A rally speeds
    up prepayments, so the pool shrinks faster and carry falls.

No funding cost and no reinvestment of cash received.
"""

from __future__ import annotations

import numpy as np

from tenorwise.curve.bootstrap import ZeroCurve
from tenorwise.instruments.bond import FixedRateBond
from tenorwise.portfolio.positions import Position

HORIZON_MONTHS = 12


def carry_12m(position: Position, curve: ZeroCurve, mortgage_spread: float) -> float:
    inst = position.instrument
    ratio = position.amortized_cost / position.face  # 1 for positions bought at par
    if isinstance(inst, FixedRateBond):
        months = min(HORIZON_MONTHS, inst.maturity_months)
        return position.amortized_cost * position.book_yield * months / HORIZON_MONTHS
    cf = inst.cash_flows(curve, mortgage_spread)
    balances = cf.balance_start[:HORIZON_MONTHS]
    return float(np.sum(balances * ratio) * position.book_yield / HORIZON_MONTHS)
