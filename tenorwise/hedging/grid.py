"""Strategy-by-scenario grid (PLAN.md section 7). Units: $ millions.

For each strategy and scenario:
  securities_delta_mv  change in the whole portfolio's value (AFS + HTM)
  swap_pnl             change in the swaps' value (they start at zero)
  net_delta_mv         securities_delta_mv + swap_pnl
  aoci_net             AFS change + swap_pnl (swaps as perfectly effective
                       fair-value hedges of the AFS book), pre-tax
  loss_avoided         = swap_pnl
  carry_given_up       = minus the swaps' 12-month carry (receive 3-month
                         floating, pay fixed); positive when the fixed rate
                         is above the floating rate
  net_carry            securities' 12-month carry + swap carry
"""

from __future__ import annotations

from dataclasses import dataclass

from tenorwise.hedging.strategies import HedgeStrategy
from tenorwise.portfolio.positions import Position
from tenorwise.portfolio.valuation import MarketContext
from tenorwise.scenarios.definitions import Scenario
from tenorwise.scenarios.revaluation import ScenarioResult, run_scenario


@dataclass(frozen=True)
class GridCell:
    strategy_id: str
    scenario_id: str
    securities_delta_mv: float
    afs_delta_mv: float
    swap_pnl: float
    net_delta_mv: float
    aoci_net: float
    loss_avoided: float
    carry_given_up: float
    net_carry: float


def grid_cells(strategies: list[HedgeStrategy], result: ScenarioResult, ctx: MarketContext) -> list[GridCell]:
    cells = []
    for st in strategies:
        swap_pnl = float(sum(s.value(result.curve) - s.value(ctx.base) for s in st.swaps))
        swap_carry = float(sum(s.carry_12m(result.curve) for s in st.swaps))
        cells.append(
            GridCell(
                strategy_id=st.id,
                scenario_id=result.scenario.id,
                securities_delta_mv=result.total.delta_mv,
                afs_delta_mv=result.total.aoci_impact,
                swap_pnl=swap_pnl,
                net_delta_mv=result.total.delta_mv + swap_pnl,
                aoci_net=result.total.aoci_impact + swap_pnl,
                loss_avoided=swap_pnl,
                carry_given_up=0.0 - swap_carry,
                net_carry=result.total.carry_12m + swap_carry,
            )
        )
    return cells


def run_grid(
    strategies: list[HedgeStrategy], scenarios: list[Scenario], positions: list[Position], ctx: MarketContext
) -> list[GridCell]:
    cells: list[GridCell] = []
    for sc in scenarios:
        cells.extend(grid_cells(strategies, run_scenario(sc, positions, ctx), ctx))
    return cells
