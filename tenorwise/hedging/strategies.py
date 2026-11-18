"""Hedge strategies sized against the AFS book (PLAN.md section 7).

Why AFS only: AFS losses reach AOCI (equity), and under current US GAAP the
interest-rate risk of HTM securities cannot be designated as a hedged risk
(ASC 815-20-25-43, decision log D-045). The swaps are treated as perfectly
effective fair-value hedges, so AOCI net of hedges = AFS change + swap gain/loss.

Strategies are sized once on the base curve and never rebalanced:
  unhedged   no swaps
  dv01_50    one 5-year pay-fixed swap offsetting half the AFS DV01
  dv01_full  one 5-year swap offsetting all of it
  key_rate   2-, 5- and 10-year swaps solving a 3x3 system so the hedged AFS
             book has zero key-rate DV01 at 2y, at 5y, and at 10y + 30y
             combined (the 30-year bucket is hedged by proxy with the 10-year
             swap; the leftover 10s-30s curve risk is in LIMITATIONS.md)

DV01 sign convention: positive = loses value when rates rise. AFS bonds have
positive DV01; pay-fixed swaps have negative DV01.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tenorwise.analytics.risk import KEY_RATE_BUCKETS, RiskMeasures, risk_measures
from tenorwise.instruments.swap import PayFixedSwap
from tenorwise.portfolio.valuation import Aggregate, MarketContext, PortfolioValuation

HEDGE_TENORS_MONTHS = (24, 60, 120)
DV01_HEDGE_TENOR_MONTHS = 60


@dataclass(frozen=True)
class HedgeStrategy:
    id: str
    name: str
    swaps: tuple[PayFixedSwap, ...]
    swap_dv01: tuple[float, ...]  # $M per bp, per swap (negative for pay-fixed)
    swap_key_rate_dv01: tuple[dict[int, float], ...]
    dv01_after: float  # AFS + swaps
    key_rate_dv01_after: dict[int, float]  # AFS + swaps
    swap_spread: float


def afs_risk(pv: PortfolioValuation) -> Aggregate:
    return pv.by_class["AFS"]


def unit_swap_risk(ctx: MarketContext, tenor_months: int, swap_spread: float) -> tuple[PayFixedSwap, RiskMeasures]:
    """Risk of a $1M-notional par swap; scales linearly with notional."""
    unit = PayFixedSwap.at_par(ctx.base, tenor_months, notional=1.0, swap_spread=swap_spread)
    return unit, risk_measures(unit.value, ctx.curves)


def _strategy(
    id_: str, name: str, afs: Aggregate, ctx: MarketContext, notionals: dict[int, float], swap_spread: float
) -> HedgeStrategy:
    swaps, dv01s, krs = [], [], []
    for tenor, notional in notionals.items():
        unit, r = unit_swap_risk(ctx, tenor, swap_spread)
        swaps.append(PayFixedSwap.at_par(ctx.base, tenor, notional=notional, swap_spread=swap_spread))
        dv01s.append(notional * r.dv01)
        krs.append({b: notional * r.key_rate_dv01[b] for b in KEY_RATE_BUCKETS})
    return HedgeStrategy(
        id=id_,
        name=name,
        swaps=tuple(swaps),
        swap_dv01=tuple(dv01s),
        swap_key_rate_dv01=tuple(krs),
        dv01_after=afs.dv01 + sum(dv01s),
        key_rate_dv01_after={b: afs.key_rate_dv01[b] + sum(k[b] for k in krs) for b in KEY_RATE_BUCKETS},
        swap_spread=swap_spread,
    )


def key_rate_notionals(afs: Aggregate, ctx: MarketContext, swap_spread: float) -> dict[int, float]:
    """Solve A n = -b: rows are the 2y, 5y and (10y + 30y) buckets, columns the 2/5/10y swaps."""
    columns = []
    for tenor in HEDGE_TENORS_MONTHS:
        _, r = unit_swap_risk(ctx, tenor, swap_spread)
        kr = r.key_rate_dv01
        columns.append([kr[2], kr[5], kr[10] + kr[30]])
    a = np.array(columns).T
    b = np.array([afs.key_rate_dv01[2], afs.key_rate_dv01[5], afs.key_rate_dv01[10] + afs.key_rate_dv01[30]])
    n = np.linalg.solve(a, -b)
    return {tenor: float(x) for tenor, x in zip(HEDGE_TENORS_MONTHS, n)}


def build_strategies(pv: PortfolioValuation, ctx: MarketContext, swap_spread: float = 0.0) -> list[HedgeStrategy]:
    afs = afs_risk(pv)
    _, five = unit_swap_risk(ctx, DV01_HEDGE_TENOR_MONTHS, swap_spread)
    full_notional = -afs.dv01 / five.dv01
    return [
        _strategy("unhedged", "Unhedged", afs, ctx, {}, swap_spread),
        _strategy("dv01_50", "50% DV01 hedge", afs, ctx, {DV01_HEDGE_TENOR_MONTHS: 0.5 * full_notional}, swap_spread),
        _strategy("dv01_full", "Full DV01 hedge", afs, ctx, {DV01_HEDGE_TENOR_MONTHS: full_notional}, swap_spread),
        _strategy("key_rate", "Key-rate-matched hedge", afs, ctx, key_rate_notionals(afs, ctx, swap_spread), swap_spread),
    ]
