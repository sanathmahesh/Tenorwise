"""Revalue the portfolio under a scenario (PLAN.md section 6, Scenarios).

Per position, sector, class and in total:
  delta_mv          shocked market value - base market value ($M)
  delta_mv_pct      delta_mv / base market value (fraction; the API shows percent)
  aoci_impact       the AFS part of delta_mv, pre-tax. Available-for-sale
                    securities are marked to market through AOCI, part of equity.
  htm_unrecognized  the HTM part of delta_mv: a real economic change that is
                    not recognized in the accounts (HTM is carried at amortized cost)
  carry_12m         gross interest income over 12 months under the scenario ($M)

Units: $ millions.
"""

from __future__ import annotations

from dataclasses import dataclass

from tenorwise.curve.bootstrap import ZeroCurve
from tenorwise.curve.shocks import ShockedCurve, apply_shock
from tenorwise.portfolio.positions import Position
from tenorwise.portfolio.sources import CLASSES, SECTORS
from tenorwise.portfolio.valuation import MarketContext, price_function
from tenorwise.scenarios.carry import carry_12m
from tenorwise.scenarios.definitions import Scenario


@dataclass(frozen=True)
class PositionResult:
    position: Position
    base_mv: float
    shocked_mv: float
    delta_mv: float
    aoci_impact: float
    htm_unrecognized: float
    carry_12m: float


@dataclass(frozen=True)
class GroupResult:
    base_mv: float
    delta_mv: float
    delta_mv_pct: float
    aoci_impact: float
    htm_unrecognized: float
    carry_12m: float


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    shocked: ShockedCurve
    positions: list[PositionResult]
    total: GroupResult
    by_sector: dict[str, GroupResult]
    by_class: dict[str, GroupResult]

    @property
    def curve(self) -> ZeroCurve:
        return self.shocked.curve

    @property
    def floor_bound(self) -> bool:
        return self.shocked.floor_bound

    @property
    def floored_tenor_months(self) -> tuple[int, ...]:
        return self.shocked.floored_tenor_months


def _group(members: list[PositionResult]) -> GroupResult:
    base = sum(m.base_mv for m in members)
    delta = sum(m.delta_mv for m in members)
    return GroupResult(
        base_mv=base,
        delta_mv=delta,
        delta_mv_pct=delta / base if base else 0.0,
        aoci_impact=sum(m.aoci_impact for m in members),
        htm_unrecognized=sum(m.htm_unrecognized for m in members),
        carry_12m=sum(m.carry_12m for m in members),
    )


def run_scenario(scenario: Scenario, positions: list[Position], ctx: MarketContext) -> ScenarioResult:
    shocked = apply_shock(ctx.par, scenario.shock_bp)
    results = []
    for p in positions:
        price = price_function(p, ctx)
        base_mv = price(ctx.base)
        shocked_mv = price(shocked.curve)
        delta = shocked_mv - base_mv
        results.append(
            PositionResult(
                position=p,
                base_mv=base_mv,
                shocked_mv=shocked_mv,
                delta_mv=delta,
                aoci_impact=delta if p.klass == "AFS" else 0.0,
                htm_unrecognized=delta if p.klass == "HTM" else 0.0,
                carry_12m=carry_12m(p, shocked.curve, ctx.mortgage.spread),
            )
        )
    return ScenarioResult(
        scenario=scenario,
        shocked=shocked,
        positions=results,
        total=_group(results),
        by_sector={s: _group([r for r in results if r.position.sector == s]) for s in SECTORS},
        by_class={k: _group([r for r in results if r.position.klass == k]) for k in CLASSES},
    )
