"""Value the model portfolio on a curve and aggregate by sector and class.

Units: $ millions; DV01 in $ millions per basis point; rates as decimals.

Per position: market value (dirty, on the curve plus the sector spread),
unrealized gain or loss (market value - amortized cost), effective duration
and convexity (curve bumps, so mortgage prepayments respond), modified
duration (from the position's own yield; labelled yield-based, D-024), DV01
and key-rate DV01s.

Aggregates: values, amortized cost, unrealized, DV01 and key-rate DV01s are
sums; duration and convexity are market-value-weighted averages; `weight` is
the share of amortized cost (the basis of the BNY mapping, D-038).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tenorwise.analytics import yield_measures as ym
from tenorwise.analytics.mbs_profile import current_coupon_pool
from tenorwise.analytics.risk import KEY_RATE_BUCKETS, RiskCurves, build_risk_curves, risk_measures
from tenorwise.curve.bootstrap import ParCurve, ZeroCurve
from tenorwise.curve.mortgage_spread import MortgageSpread
from tenorwise.instruments.bond import FixedRateBond
from tenorwise.instruments.mbs import discount_spread_for_price
from tenorwise.portfolio.positions import Position
from tenorwise.portfolio.sources import CLASSES, SECTORS, load_bny_source

# Approved sector spreads (D-037). Agency mortgage bonds are calibrated per build.
FIXED_SECTOR_SPREADS = {"treasuries": 0.0, "agency_debt": 0.0025, "ig_corporates": 0.0100}


@dataclass(frozen=True)
class MarketContext:
    par: ParCurve
    curves: RiskCurves
    mortgage: MortgageSpread
    sector_spreads: dict[str, float]

    @property
    def base(self) -> ZeroCurve:
        return self.curves.base


def build_market_context(par: ParCurve, mortgage: MortgageSpread) -> MarketContext:
    curves = build_risk_curves(par)
    pool = current_coupon_pool(curves.base, mortgage.spread)
    mbs_spread = discount_spread_for_price(pool, curves.base, mortgage.spread, target_price=100.0)
    return MarketContext(
        par=par,
        curves=curves,
        mortgage=mortgage,
        sector_spreads={**FIXED_SECTOR_SPREADS, "agency_mbs": mbs_spread},
    )


def price_function(position: Position, ctx: MarketContext) -> Callable[[ZeroCurve], float]:
    """Value in $M on any (possibly shocked) curve; spreads stay fixed (PLAN.md section 6)."""
    spread = ctx.sector_spreads[position.sector]
    inst = position.instrument
    if isinstance(inst, FixedRateBond):
        return lambda curve: inst.dirty_price(curve, spread)
    mortgage_spread = ctx.mortgage.spread
    return lambda curve: inst.price(curve, mortgage_spread, spread)


@dataclass(frozen=True)
class PositionValuation:
    position: Position
    market_value: float
    price: float  # per 100 of face
    unrealized: float
    eff_duration: float
    mod_duration: float  # yield-based
    convexity: float  # effective (curve-based)
    dv01: float
    key_rate_dv01: dict[int, float]


@dataclass(frozen=True)
class Aggregate:
    market_value: float
    amortized_cost: float
    unrealized: float
    eff_duration: float
    convexity: float
    dv01: float
    key_rate_dv01: dict[int, float]
    weight: float  # share of total amortized cost


@dataclass(frozen=True)
class PortfolioValuation:
    positions: list[PositionValuation]
    summary: Aggregate
    by_sector: dict[str, Aggregate]
    by_class: dict[str, Aggregate]
    book_yields: dict[str, dict[str, float]] = field(default_factory=dict)


def _own_yield_cash_flows(position: Position, ctx: MarketContext):
    inst = position.instrument
    if isinstance(inst, FixedRateBond):
        return inst.cash_flows()
    cf = inst.cash_flows(ctx.base, ctx.mortgage.spread)
    return cf.times, cf.total


def value_position(position: Position, ctx: MarketContext) -> PositionValuation:
    r = risk_measures(price_function(position, ctx), ctx.curves)
    times, amounts = _own_yield_cash_flows(position, ctx)
    own_yield = ym.yield_from_price(times, amounts, r.price)
    return PositionValuation(
        position=position,
        market_value=r.price,
        price=100.0 * r.price / position.face,
        unrealized=r.price - position.amortized_cost,
        eff_duration=r.eff_duration,
        mod_duration=ym.modified_duration(times, amounts, own_yield),
        convexity=r.eff_convexity,
        dv01=r.dv01,
        key_rate_dv01=dict(r.key_rate_dv01),
    )


def aggregate(members: list[PositionValuation], total_amortized_cost: float) -> Aggregate:
    mv = sum(v.market_value for v in members)
    ac = sum(v.position.amortized_cost for v in members)
    return Aggregate(
        market_value=mv,
        amortized_cost=ac,
        unrealized=mv - ac,
        eff_duration=sum(v.market_value * v.eff_duration for v in members) / mv,
        convexity=sum(v.market_value * v.convexity for v in members) / mv,
        dv01=sum(v.dv01 for v in members),
        key_rate_dv01={b: sum(v.key_rate_dv01[b] for v in members) for b in KEY_RATE_BUCKETS},
        weight=ac / total_amortized_cost,
    )


def book_yield_report(positions: list[Position]) -> dict[str, dict[str, float]]:
    """Amortized-cost-weighted book yield per class, against BNY's disclosed figure."""
    totals = load_bny_source()["maturity_distribution_and_yields"]
    bny = {
        "AFS": totals["available_for_sale_total"]["total"][1] / 100.0,
        "HTM": totals["held_to_maturity_total"]["total"][1] / 100.0,
    }
    out = {}
    for klass in CLASSES:
        members = [p for p in positions if p.klass == klass]
        model = sum(p.amortized_cost * p.book_yield for p in members) / sum(p.amortized_cost for p in members)
        out[klass] = {"model": model, "bny": bny[klass], "gap_bp": 1e4 * (model - bny[klass])}
    return out


def value_portfolio(positions: list[Position], ctx: MarketContext) -> PortfolioValuation:
    valued = [value_position(p, ctx) for p in positions]
    total_ac = sum(p.amortized_cost for p in positions)
    return PortfolioValuation(
        positions=valued,
        summary=aggregate(valued, total_ac),
        by_sector={s: aggregate([v for v in valued if v.position.sector == s], total_ac) for s in SECTORS},
        by_class={k: aggregate([v for v in valued if v.position.klass == k], total_ac) for k in CLASSES},
        book_yields=book_yield_report(positions),
    )
