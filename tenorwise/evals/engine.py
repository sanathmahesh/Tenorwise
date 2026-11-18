"""The engine, run directly, for the eval gold functions.

Gold answers must not come from the agent's tools (that would grade the tools
against themselves). This module rebuilds everything from the pinned market
fixtures with the engine's own functions: the same inputs the pinned snapshot
was built from, so the two must agree (tested).

Engine units are $ millions and decimals; gold values are converted to the
contract's units (US dollars, percent) with the same constants the snapshot uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from tenorwise.analytics.mbs_profile import (
    ProfileRow,
    current_coupon_pool,
    matching_treasury,
    mbs_profile,
    treasury_comparison,
)
from tenorwise.curve.shocks import key_rate_shock, parallel_shock
from tenorwise.hedging.grid import GridCell, grid_cells
from tenorwise.hedging.strategies import HedgeStrategy, build_strategies
from tenorwise.portfolio.positions import Position, load_positions
from tenorwise.portfolio.valuation import MarketContext, PortfolioValuation, build_market_context, value_portfolio
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.revaluation import ScenarioResult, run_scenario
from tenorwise.snapshot.build import SWAP_SPREAD, base_scenario
from tenorwise.snapshot.convert import PCT, USD
from tenorwise.snapshot.inputs import MarketInputs

__all__ = ["PCT", "USD", "EngineContext"]


@dataclass(frozen=True)
class EngineContext:
    inputs: MarketInputs
    ctx: MarketContext
    positions: list[Position]
    pv: PortfolioValuation
    scenarios: dict[str, ScenarioResult]
    strategies: dict[str, HedgeStrategy]
    cells: dict[tuple[str, str], GridCell]  # (strategy_id, scenario_id)
    mbs_rows: dict[float, ProfileRow]  # by shift in bp
    treasury_prices: dict[float, float]  # comparison Treasury price per 100, by shift in bp

    @classmethod
    def from_fixtures(cls) -> EngineContext:
        return cls.from_inputs(MarketInputs.from_fixtures())

    @classmethod
    def from_inputs(cls, inputs: MarketInputs) -> EngineContext:
        ctx = build_market_context(inputs.par, inputs.mortgage)
        positions = load_positions()
        pv = value_portfolio(positions, ctx)
        scenarios = [base_scenario(len(inputs.par.tenor_months))] + preset_scenarios(inputs.replay_shock_bp)
        results = {s.id: run_scenario(s, positions, ctx) for s in scenarios}
        strategies = build_strategies(pv, ctx, swap_spread=SWAP_SPREAD)
        cells = {(c.strategy_id, c.scenario_id): c for r in results.values() for c in grid_cells(strategies, r, ctx)}

        spread = inputs.mortgage.spread
        pool = current_coupon_pool(ctx.base, spread)
        profile = mbs_profile(pool, ctx.par, spread, ctx.sector_spreads["agency_mbs"])
        base_row = next(r for r in profile if r.shift_bp == 0)
        tsy = matching_treasury(ctx.par, base_row.eff_duration)
        return cls(
            inputs=inputs, ctx=ctx, positions=positions, pv=pv, scenarios=results,
            strategies={s.id: s for s in strategies}, cells=cells,
            mbs_rows={r.shift_bp: r for r in profile},
            treasury_prices=dict(treasury_comparison(tsy, ctx.par)),
        )

    # ------------------------------------------------------------------ custom shocks

    def _custom(self, shock: tuple[float, ...]) -> ScenarioResult:
        return run_scenario(Scenario("custom", "custom", "custom", shock), self.positions, self.ctx)

    def custom_parallel(self, bp: float) -> ScenarioResult:
        return self._custom(tuple(float(x) for x in parallel_shock(bp, len(self.inputs.par.tenor_months))))

    def custom_key_rate(self, b2: float, b5: float, b10: float, b30: float) -> ScenarioResult:
        tenors = self.inputs.par.tenor_months
        shock = (key_rate_shock(2, b2, tenors) + key_rate_shock(5, b5, tenors)
                 + key_rate_shock(10, b10, tenors) + key_rate_shock(30, b30, tenors))
        return self._custom(tuple(float(x) for x in shock))

    def custom_cells(self, result: ScenarioResult) -> dict[str, GridCell]:
        return {c.strategy_id: c for c in grid_cells(list(self.strategies.values()), result, self.ctx)}

    # ------------------------------------------------------------------ lookups

    def par_yield(self, tenor_months: int) -> float:
        par = self.inputs.par
        return par.par_yields[par.tenor_months.index(tenor_months)]

    def position(self, position_id: str):
        return next(v for v in self.pv.positions if v.position.id == position_id)
