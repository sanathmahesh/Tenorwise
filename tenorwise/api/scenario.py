"""POST /api/scenario: rebuild the market from the snapshot's inputs and run a custom shock.

Reads data/snapshot/v1/inputs.json (written at build time, full precision) on
every request; nothing is cached and nothing is written (ground rule 7).
Returns one scenarios[] entry plus its hedge grid rows (PLAN.md section 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from tenorwise.curve.bootstrap import ParCurve
from tenorwise.curve.mortgage_spread import MortgageSpread
from tenorwise.curve.shocks import key_rate_shock, parallel_shock
from tenorwise.hedging.grid import grid_cells
from tenorwise.instruments.swap import PayFixedSwap
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context
from tenorwise.scenarios.definitions import Scenario
from tenorwise.scenarios.revaluation import run_scenario
from tenorwise.snapshot.convert import scenario_response
from tenorwise.snapshot.models import InputsFile, ScenarioRequest
from tenorwise.snapshot.serialize import to_jsonable
from tenorwise.snapshot.store import read_json


@dataclass(frozen=True)
class StoredHedge:
    """The fields of a sized hedge strategy that the grid needs."""

    id: str
    name: str
    swaps: tuple[PayFixedSwap, ...]


def custom_scenario(req: ScenarioRequest, n_tenors: int) -> Scenario:
    if req.parallel_bp is not None:
        bp = float(req.parallel_bp)
        return Scenario(
            "custom", f"Custom: {bp:+g} bp parallel", f"Custom parallel shift of {bp:+g} bp.",
            tuple(float(x) for x in parallel_shock(bp, n_tenors)),
        )
    k = req.key_rate_bp
    shock = key_rate_shock(2, k.y2) + key_rate_shock(5, k.y5) + key_rate_shock(10, k.y10) + key_rate_shock(30, k.y30)
    return Scenario(
        "custom", "Custom: key-rate shock",
        f"Custom key-rate shock: 2y {k.y2:+g}, 5y {k.y5:+g}, 10y {k.y10:+g}, 30y {k.y30:+g} bp.",
        tuple(float(x) for x in shock),
    )


def run_custom(req: ScenarioRequest) -> Any | None:
    raw = read_json("inputs.json")
    if raw is None:
        return None
    return custom_from_inputs(req, raw)


def custom_from_inputs(req: ScenarioRequest, raw_inputs: dict) -> Any:
    """The custom scenario on the build's inputs; shared by the API and the agent's tools."""
    inputs = InputsFile.model_validate(raw_inputs)
    par = ParCurve(
        data_date=date.fromisoformat(inputs.data_date),
        tenor_months=tuple(inputs.par_tenor_months),
        par_yields=tuple(inputs.par_yields),
    )
    mortgage = MortgageSpread(
        date=date.fromisoformat(inputs.mortgage.date),
        mortgage_rate=inputs.mortgage.mortgage_rate,
        ten_year_yield=inputs.mortgage.ten_year_yield,
        spread=inputs.mortgage.spread,
    )
    ctx = build_market_context(par, mortgage)
    hedges = [
        StoredHedge(
            id=s.id,
            name=s.name,
            swaps=tuple(PayFixedSwap(w.tenor_months, w.notional_musd, w.fixed_rate, w.swap_spread) for w in s.swaps),
        )
        for s in inputs.strategies
    ]
    result = run_scenario(custom_scenario(req, len(par.tenor_months)), load_positions(), ctx)
    return to_jsonable(scenario_response(result, grid_cells(hedges, result, ctx), par))
