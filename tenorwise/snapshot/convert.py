"""Engine objects -> contract models (units converted here and only here).

Engine units: $ millions, decimals. Contract units: US dollars, percent.
Used by the snapshot build and by the API, so both report identical numbers.
"""

from __future__ import annotations

from tenorwise.curve.bootstrap import ParCurve, ZeroCurve
from tenorwise.hedging.grid import GridCell
from tenorwise.hedging.strategies import HedgeStrategy
from tenorwise.portfolio.sources import SECTOR_NAMES
from tenorwise.portfolio.valuation import Aggregate, PortfolioValuation, PositionValuation
from tenorwise.scenarios.revaluation import GroupResult, ScenarioResult
from tenorwise.snapshot import models as m

USD = 1e6  # $ millions -> US dollars
PCT = 100.0  # decimal -> percent
CLASS_NAMES = {"AFS": "Available-for-sale", "HTM": "Held-to-maturity"}


def key_rates(d: dict[int, float]) -> m.KeyRateDV01:
    return m.KeyRateDV01(y2=USD * d[2], y5=USD * d[5], y10=USD * d[10], y30=USD * d[30])


def curve_points(curve: ZeroCurve) -> list[m.CurvePoint]:
    return [
        m.CurvePoint(
            tenor_years=months / 12.0,
            par_yield=PCT * y,
            zero_rate=PCT * z,
            discount_factor=curve.discount_factor(months / 12.0),
        )
        for months, y, z in zip(curve.tenor_months, curve.par.par_yields, curve.zero_rates)
    ]


# ------------------------------------------------------------------ portfolio


def _risk(agg: Aggregate) -> dict:
    return dict(
        market_value=USD * agg.market_value,
        amortized_cost=USD * agg.amortized_cost,
        unrealized=USD * agg.unrealized,
        eff_duration=agg.eff_duration,
        convexity=agg.convexity,
        dv01=USD * agg.dv01,
        key_rate_dv01=key_rates(agg.key_rate_dv01),
    )


def group_row(id_: str, name: str, agg: Aggregate) -> m.GroupRow:
    return m.GroupRow(id=id_, name=name, weight=PCT * agg.weight, **_risk(agg))


def position_row(v: PositionValuation) -> m.PositionRow:
    p = v.position
    return m.PositionRow(
        id=p.id,
        name=p.name,
        sector=p.sector,
        klass=p.klass,
        face=USD * p.face,
        coupon=PCT * p.coupon,
        maturity_years=p.maturity_months / 12.0,
        book_yield=PCT * p.book_yield,
        price=v.price,
        market_value=USD * v.market_value,
        amortized_cost=USD * p.amortized_cost,
        unrealized=USD * v.unrealized,
        eff_duration=v.eff_duration,
        mod_duration=v.mod_duration,
        convexity=v.convexity,
        dv01=USD * v.dv01,
        key_rate_dv01=key_rates(v.key_rate_dv01),
        stylized=p.stylized,
        proxy_for=p.proxy_for,
    )


def portfolio_model(pv: PortfolioValuation, data_date: str, source: m.Source) -> m.Portfolio:
    return m.Portfolio(
        data_date=data_date,
        summary=m.PortfolioSummary(**_risk(pv.summary)),
        by_sector=[group_row(s, SECTOR_NAMES[s], g) for s, g in pv.by_sector.items()],
        by_class=[group_row(k, CLASS_NAMES[k], g) for k, g in pv.by_class.items()],
        positions=[position_row(v) for v in pv.positions],
        source=source,
    )


# ------------------------------------------------------------------ scenarios and hedges


def _totals(g: GroupResult) -> dict:
    return dict(
        delta_mv=USD * g.delta_mv,
        delta_mv_pct=PCT * g.delta_mv_pct,
        aoci_impact=USD * g.aoci_impact,
        htm_unrecognized=USD * g.htm_unrecognized,
        carry_12m=USD * g.carry_12m,
    )


def scenario_entry(result: ScenarioResult) -> m.ScenarioEntry:
    sc = result.scenario
    tenors = result.curve.tenor_months
    return m.ScenarioEntry(
        id=sc.id,
        name=sc.name,
        description=sc.description,
        shock_bp_by_tenor=[m.ShockPoint(tenor_years=t / 12.0, shock_bp=b) for t, b in zip(tenors, sc.shock_bp)],
        total=m.ScenarioTotals(**_totals(result.total)),
        by_sector=[m.ScenarioGroup(id=s, name=SECTOR_NAMES[s], **_totals(g)) for s, g in result.by_sector.items()],
        by_class=[m.ScenarioGroup(id=k, name=CLASS_NAMES[k], **_totals(g)) for k, g in result.by_class.items()],
        shocked_curve=curve_points(result.curve),
        floor_bound=result.floor_bound,
        floored_tenor_years=[t / 12.0 for t in result.floored_tenor_months],
    )


def grid_row(c: GridCell) -> m.GridRow:
    return m.GridRow(
        strategy_id=c.strategy_id,
        scenario_id=c.scenario_id,
        securities_delta_mv=USD * c.securities_delta_mv,
        swap_pnl=USD * c.swap_pnl,
        net_delta_mv=USD * c.net_delta_mv,
        aoci_net=USD * c.aoci_net,
        loss_avoided=USD * c.loss_avoided,
        carry_given_up=USD * c.carry_given_up,
        net_carry=USD * c.net_carry,
    )


def strategy_row(st: HedgeStrategy) -> m.StrategyRow:
    return m.StrategyRow(
        id=st.id,
        name=st.name,
        swaps=[
            m.SwapRow(tenor_years=s.tenor_years, notional=USD * s.notional, fixed_rate=PCT * s.fixed_rate, dv01=USD * d)
            for s, d in zip(st.swaps, st.swap_dv01)
        ],
        key_rate_dv01_after=key_rates(st.key_rate_dv01_after),
        dv01_after=USD * st.dv01_after,
    )


def scenario_response(result: ScenarioResult, cells: list[GridCell], par: ParCurve) -> m.ScenarioResponse:
    return m.ScenarioResponse(
        data_date=par.data_date.isoformat(),
        scenario=scenario_entry(result),
        grid=[grid_row(c) for c in cells],
    )
