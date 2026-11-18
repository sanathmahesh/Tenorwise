"""The analyst's tools (PLAN.md section 9). All read-only; all wrap the engine's outputs.

Every figure a tool returns goes into the ledger and reaches the model only as
{"id", "label", "display"}: there are no bare numbers in tool results. Tool
arguments become context numbers. Invalid arguments come back to the model as
{"error": ...}, never as an exception, and leave the ledger untouched.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from tenorwise.agent.data import AgentData
from tenorwise.agent.ledger import Ledger
from tenorwise.api.scenario import custom_from_inputs
from tenorwise.snapshot.methods import METHODS
from tenorwise.snapshot.models import ScenarioRequest

SECTORS = ("treasuries", "agency_mbs", "agency_debt", "ig_corporates")
SCENARIO_IDS = ("base", "parallel_up_100", "parallel_down_100", "parallel_up_200", "parallel_down_200",
                "bear_steepener", "bull_flattener", "replay_2022")
STRATEGY_IDS = ("unhedged", "dv01_50", "dv01_full", "key_rate")
COMMENTARY_HEADINGS = ("Positioning", "Rate sensitivity", "Scenario results", "Hedging trade-off", "Caveats")


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NoArgs(Args):
    pass


class PortfolioArgs(Args):
    group: Literal["total", "sector", "class"] = Field("total", description="total, by sector, or by accounting class")


class PositionsArgs(Args):
    sector: Literal["treasuries", "agency_mbs", "agency_debt", "ig_corporates"] | None = None
    accounting_class: Literal["AFS", "HTM"] | None = None
    position_id: str | None = Field(None, description="e.g. UST-A3")


class KeyRateBp(Args):
    y2: float = Field(alias="2", ge=-300, le=300)
    y5: float = Field(alias="5", ge=-300, le=300)
    y10: float = Field(alias="10", ge=-300, le=300)
    y30: float = Field(alias="30", ge=-300, le=300)


class ScenarioArgs(Args):
    """Exactly one of: a preset scenario_id, a custom parallel_bp, or custom key_rate_bp."""

    scenario_id: Literal["base", "parallel_up_100", "parallel_down_100", "parallel_up_200", "parallel_down_200",
                         "bear_steepener", "bull_flattener", "replay_2022"] | None = None
    parallel_bp: float | None = Field(None, ge=-300, le=300)
    key_rate_bp: KeyRateBp | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> ScenarioArgs:
        given = sum(x is not None for x in (self.scenario_id, self.parallel_bp, self.key_rate_bp))
        if given != 1:
            raise ValueError("give exactly one of scenario_id, parallel_bp or key_rate_bp")
        return self


class HedgeArgs(Args):
    strategy_id: Literal["unhedged", "dv01_50", "dv01_full", "key_rate"]


class MethodArgs(Args):
    method_id: Literal[tuple(METHODS)]  # type: ignore[valid-type]


class DeriveArgs(Args):
    operation: Literal["sum", "difference", "ratio", "percent_change"] = Field(
        description="sum: a+b+...; difference: a-b; ratio: a/b; percent_change: (b-a)/|a| x 100"
    )
    operands: list[str] = Field(min_length=1, description="value IDs from earlier tool results, e.g. ['v3', 'v7']")
    label: str = Field(min_length=1, max_length=120, description="what the result is")


class SubmitAnswerArgs(Args):
    status: Literal["answered", "cannot_answer"]
    answer_md: str = Field(min_length=1, max_length=6000)


class Section(Args):
    heading: Literal["Positioning", "Rate sensitivity", "Scenario results", "Hedging trade-off", "Caveats"]
    body_md: str = Field(min_length=1, max_length=3000)


class SubmitCommentaryArgs(Args):
    sections: list[Section]

    @field_validator("sections")
    @classmethod
    def fixed_sections(cls, v: list[Section]) -> list[Section]:
        if tuple(s.heading for s in v) != COMMENTARY_HEADINGS:
            raise ValueError(f"sections must be exactly, in order: {', '.join(COMMENTARY_HEADINGS)}")
        return v


DESCRIPTIONS = {
    "get_curve": "Treasury par yields and zero rates at the 11 curve points on the market data date.",
    "get_portfolio_summary": "Portfolio market value, amortized cost, unrealized gain/loss, effective duration, convexity, DV01 and key-rate DV01s; in total, by sector or by accounting class (AFS/HTM).",
    "get_positions": "Positions with face, coupon, maturity, book yield, price, market value, unrealized, duration and DV01. Filter by sector, accounting class or position ID.",
    "run_scenario": "Change in market value, AOCI impact (AFS), HTM change not recognized and 12-month carry for a preset scenario or a custom parallel/key-rate shock (-300 to +300 bp).",
    "compare_hedges": "For one scenario, each hedge strategy's AOCI net of hedges, net change, loss avoided, carry given up and net carry.",
    "get_hedge": "One hedge strategy's swaps (tenor, notional, fixed rate, DV01) and the AFS book's DV01 and key-rate DV01s after hedging.",
    "get_mbs_profile": "The stylized agency mortgage pool's price, duration, convexity, average life and prepayment speed across rate shifts, with the mortgage rate and model parameters.",
    "get_methodology": "Plain-English explanation and formula of one calculation method.",
    "derive": "Calculator for figures no other tool returns: sum, difference, ratio or percent change of value IDs. Use it instead of doing arithmetic.",
    "submit_answer": "Submit the final answer. Every number must be copied from a display string and followed by its [[v…]] tag.",
    "submit_commentary": "Submit the commentary draft as exactly five sections: Positioning, Rate sensitivity, Scenario results, Hedging trade-off, Caveats.",
}
ARG_MODELS: dict[str, type[Args]] = {
    "get_curve": NoArgs,
    "get_portfolio_summary": PortfolioArgs,
    "get_positions": PositionsArgs,
    "run_scenario": ScenarioArgs,
    "compare_hedges": ScenarioArgs,
    "get_hedge": HedgeArgs,
    "get_mbs_profile": NoArgs,
    "get_methodology": MethodArgs,
    "derive": DeriveArgs,
    "submit_answer": SubmitAnswerArgs,
    "submit_commentary": SubmitCommentaryArgs,
}
DATA_TOOLS = ("get_curve", "get_portfolio_summary", "get_positions", "run_scenario", "compare_hedges",
              "get_hedge", "get_mbs_profile", "get_methodology", "derive")
SUBMIT_TOOL = {"ask": "submit_answer", "commentary": "submit_commentary"}


def _inline(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve $refs so the schema is self-contained (some providers reject $defs)."""
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


def tool_specs(mode: Literal["ask", "commentary"]) -> list[dict[str, Any]]:
    names = list(DATA_TOOLS) + [SUBMIT_TOOL[mode]]
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": DESCRIPTIONS[name],
                "parameters": _inline(ARG_MODELS[name].model_json_schema(by_alias=True)),
            },
        }
        for name in names
    ]


# ------------------------------------------------------------------ helpers


class _Out:
    def __init__(self, tool: str, args: dict[str, Any], ledger: Ledger, data: AgentData):
        self.tool, self.args, self.ledger = tool, args, ledger
        self.result: dict[str, Any] = {"tool": tool, "data_date": data.data_date, "values": []}

    def value(self, value: float, unit: str, label: str, method: str, inputs: list[str] | None = None) -> None:
        v = self.ledger.add(value, unit, label, tool=self.tool, args=self.args, method=method, inputs=inputs or [])
        self.result["values"].append({"id": v.id, "label": v.label, "display": v.display})

    def note(self, text: str) -> None:
        self.result.setdefault("notes", []).append(text)


def _tenor(years: float) -> str:
    return f"{round(years * 12)}M" if years < 1 else f"{years:g}Y"


def _kr(out: _Out, prefix: str, kr: dict[str, float], method: str) -> None:
    for b in ("2", "5", "10", "30"):
        out.value(kr[b], "usd_per_bp", f"{prefix} key-rate DV01, {b}y bucket", method)


def _risk_rows(out: _Out, name: str, g: dict[str, Any], weight: bool) -> None:
    out.value(g["market_value"], "usd", f"{name} market value", "portfolio_aggregate")
    out.value(g["amortized_cost"], "usd", f"{name} amortized cost", "amortized_cost")
    out.value(g["unrealized"], "usd", f"{name} unrealized gain or loss", "unrealized")
    out.value(g["eff_duration"], "years", f"{name} effective duration", "eff_duration")
    out.value(g["convexity"], "number", f"{name} effective convexity", "eff_convexity")
    out.value(g["dv01"], "usd_per_bp", f"{name} DV01", "dv01")
    if weight:
        out.value(g["weight"], "pct", f"{name} weight (share of amortized cost)", "portfolio_aggregate")


def _scenario_entry(args: ScenarioArgs, data: AgentData) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if args.scenario_id is not None:
        entry = next(s for s in data.scenarios["scenarios"] if s["id"] == args.scenario_id)
        rows = [g for g in data.hedges["grid"] if g["scenario_id"] == args.scenario_id]
        return entry, rows
    req = ScenarioRequest(
        parallel_bp=args.parallel_bp,
        key_rate_bp=args.key_rate_bp.model_dump(by_alias=True) if args.key_rate_bp else None,
    )
    body = custom_from_inputs(req, data.inputs)
    return body["scenario"], body["grid"]


def _register_scenario_context(ledger: Ledger, args: ScenarioArgs, entry: dict[str, Any]) -> None:
    if args.parallel_bp is not None:
        ledger.add_context(args.parallel_bp, "bp", "custom parallel shift")
    if args.key_rate_bp is not None:
        for v in args.key_rate_bp.model_dump().values():
            ledger.add_context(v, "bp", "custom key-rate shock")
    for p in entry["shock_bp_by_tenor"]:
        ledger.add_context(p["shock_bp"], "bp", f"{entry['name']} shock")


# ------------------------------------------------------------------ tools


def _get_curve(out: _Out, args: NoArgs, data: AgentData) -> None:
    for p in data.curve["points"]:
        t = _tenor(p["tenor_years"])
        out.value(p["par_yield"], "pct", f"{t} Treasury par yield", "par_yield")
        out.value(p["zero_rate"], "pct", f"{t} zero rate", "zero_rate")


def _get_portfolio_summary(out: _Out, args: PortfolioArgs, data: AgentData) -> None:
    p = data.portfolio
    if args.group == "total":
        _risk_rows(out, "Portfolio", p["summary"], weight=False)
        _kr(out, "Portfolio", p["summary"]["key_rate_dv01"], "key_rate_dv01")
    else:
        for g in p["by_sector" if args.group == "sector" else "by_class"]:
            _risk_rows(out, g["name"], g, weight=True)
    out.note("Agency mortgage bonds are stylized. IG corporates is a proxy for BNY's fixed-rate credit holdings.")


def _get_positions(out: _Out, args: PositionsArgs, data: AgentData) -> None:
    rows = [
        x for x in data.portfolio["positions"]
        if (args.sector is None or x["sector"] == args.sector)
        and (args.accounting_class is None or x["class"] == args.accounting_class)
        and (args.position_id is None or x["id"] == args.position_id)
    ]
    if not rows:
        raise ValueError("no position matches those filters")
    full = len(rows) <= 12
    out.result["positions"] = []
    for x in rows:
        out.result["positions"].append(f"{x['id']}: {x['name']} [{x['class']}]" + (" (stylized)" if x["stylized"] else ""))
        n = x["id"]
        out.value(x["market_value"], "usd", f"{n} market value", "bond_price" if not x["stylized"] else "mbs_price")
        out.value(x["unrealized"], "usd", f"{n} unrealized gain or loss", "unrealized")
        out.value(x["book_yield"], "pct", f"{n} book yield", "amortized_cost")
        out.value(x["eff_duration"], "years", f"{n} effective duration", "eff_duration")
        out.value(x["dv01"], "usd_per_bp", f"{n} DV01", "dv01")
        if full:
            out.value(x["face"], "usd", f"{n} face", "amortized_cost")
            out.value(x["coupon"], "pct", f"{n} coupon", "bond_price")
            out.value(x["maturity_years"], "years", f"{n} remaining maturity", "bond_price")
            out.value(x["price"], "price", f"{n} price per 100", "bond_price" if not x["stylized"] else "mbs_price")
            out.value(x["amortized_cost"], "usd", f"{n} amortized cost", "amortized_cost")
            out.value(x["mod_duration"], "years", f"{n} modified duration (yield-based)", "mod_duration")
            out.value(x["convexity"], "number", f"{n} effective convexity", "eff_convexity")
    if not full:
        out.note("Many positions matched, so only the main fields are shown; filter to see face, coupon, maturity and price.")


def _run_scenario(out: _Out, args: ScenarioArgs, data: AgentData) -> None:
    entry, _ = _scenario_entry(args, data)
    _register_scenario_context(out.ledger, args, entry)
    out.result["scenario"] = f"{entry['name']}: {entry['description']}"
    t = entry["total"]
    out.value(t["delta_mv"], "usd", "Change in market value, total", "scenario_change")
    out.value(t["delta_mv_pct"], "pct", "Change in market value, % of base", "scenario_change")
    out.value(t["aoci_impact"], "usd", "AOCI impact (AFS change, pre-tax)", "aoci_impact")
    out.value(t["htm_unrecognized"], "usd", "HTM change, not recognized", "htm_unrecognized")
    out.value(t["carry_12m"], "usd", "12-month carry", "carry_12m")
    for g in entry["by_sector"] + entry["by_class"]:
        out.value(g["delta_mv"], "usd", f"Change in market value, {g['name']}", "scenario_change")
    if entry["floor_bound"]:
        out.note("The 0% floor on par yields binds in this scenario.")


def _compare_hedges(out: _Out, args: ScenarioArgs, data: AgentData) -> None:
    entry, rows = _scenario_entry(args, data)
    _register_scenario_context(out.ledger, args, entry)
    names = {s["id"]: s["name"] for s in data.hedges["strategies"]}
    out.result["scenario"] = entry["name"]
    for g in rows:
        n = names[g["strategy_id"]]
        out.value(g["aoci_net"], "usd", f"{n}: AOCI net of hedges", "aoci_net")
        out.value(g["net_delta_mv"], "usd", f"{n}: net change in value (securities + swaps)", "scenario_change")
        out.value(g["loss_avoided"], "usd", f"{n}: loss avoided (swap gain or loss)", "swap_value")
        out.value(g["carry_given_up"], "usd", f"{n}: carry given up over 12 months", "carry_given_up")
        out.value(g["net_carry"], "usd", f"{n}: net 12-month carry", "carry_12m")
    out.note("Hedges cover the AFS book only; swaps are treated as perfectly effective fair-value hedges.")


def _get_hedge(out: _Out, args: HedgeArgs, data: AgentData) -> None:
    h = data.hedges
    st = next(s for s in h["strategies"] if s["id"] == args.strategy_id)
    out.result["strategy"] = st["name"]
    out.value(h["afs_dv01"], "usd_per_bp", "AFS book DV01 before hedging", "dv01")
    out.value(h["swap_spread_bp"], "bp", "Swap curve spread over the Treasury curve (assumption)", "swap_par_rate")
    for w in st["swaps"]:
        t = f"{w['tenor_years']:g}-year swap"
        out.ledger.add_context(w["tenor_years"], "years", "swap tenor")
        out.value(w["notional"], "usd", f"{t} notional", "hedge_sizing")
        out.value(w["fixed_rate"], "pct", f"{t} fixed rate", "swap_par_rate")
        out.value(w["dv01"], "usd_per_bp", f"{t} DV01", "dv01")
    out.value(st["dv01_after"], "usd_per_bp", "AFS DV01 after hedging", "hedge_sizing")
    _kr(out, "After hedging,", st["key_rate_dv01_after"], "hedge_sizing")


def _get_mbs_profile(out: _Out, args: NoArgs, data: AgentData) -> None:
    m = data.mbs
    out.note(m["stylized_note"])
    p, r, pm = m["pool"], m["mortgage_rate"], m["prepayment_model"]
    out.value(p["wac"], "pct", "Pool gross coupon (WAC)", "mbs_cash_flows")
    out.value(p["net_coupon"], "pct", "Pool net coupon", "mbs_cash_flows")
    out.value(p["age_months"], "months", "Pool age", "mbs_cash_flows")
    out.value(p["remaining_months"], "months", "Pool remaining term", "mbs_cash_flows")
    out.value(p["discount_spread_bp"], "bp", "Discount spread that prices the pool at par", "mbs_price")
    out.value(r["mortgage_rate"], "pct", "Mortgage rate (Optimal Blue index)", "mortgage_spread")
    out.value(r["spread"], "pct", "Mortgage spread over the 10-year Treasury", "mortgage_spread")
    out.value(pm["cpr_min"], "pct", "Minimum CPR (illustrative)", "mbs_cash_flows")
    out.value(pm["cpr_max"], "pct", "Maximum CPR (illustrative)", "mbs_cash_flows")
    tsy = {row["shift_bp"]: row["price"] for row in m["comparison_treasury"]}
    for row in m["profile"]:
        s = row["shift_bp"]
        out.ledger.add_context(s, "bp", "profile shift")
        label = f"at {s:+g} bp"
        out.value(row["price"], "price", f"Pool price per 100 {label}", "mbs_price")
        out.value(row["eff_duration"], "years", f"Pool effective duration {label}", "eff_duration")
        out.value(row["eff_convexity"], "number", f"Pool effective convexity {label}", "eff_convexity")
        out.value(row["avg_life_years"], "years", f"Pool average life {label}", "avg_life")
        out.value(row["cpr"], "pct", f"Pool CPR {label}", "mbs_cash_flows")
        out.value(tsy[s], "price", f"Comparison Treasury price per 100 {label}", "bond_price")


def _get_methodology(out: _Out, args: MethodArgs, data: AgentData) -> None:
    m = data.methods["methods"][args.method_id]
    out.result.update({"name": m["name"], "plain_english": m["plain_english"], "formula": m["formula"]})


def _derive(out: _Out, args: DeriveArgs, data: AgentData) -> None:
    led = out.ledger
    missing = [o for o in args.operands if o not in led.values]
    if missing:
        raise ValueError(f"unknown value IDs: {', '.join(missing)}")
    vals = [led.values[o] for o in args.operands]
    op = args.operation
    if op == "sum":
        if len(vals) < 2 or len({v.unit for v in vals}) != 1:
            raise ValueError("sum needs two or more values with the same unit")
        result, unit = sum(v.value for v in vals), vals[0].unit
    else:
        if len(vals) != 2:
            raise ValueError(f"{op} needs exactly two values")
        a, b = vals
        if op == "difference":
            if a.unit != b.unit:
                raise ValueError("difference needs values with the same unit")
            result, unit = a.value - b.value, a.unit
        elif op == "ratio":
            if b.value == 0:
                raise ValueError("cannot divide by zero")
            if a.unit == b.unit:
                result, unit = a.value / b.value, "number"
            elif (a.unit, b.unit) == ("usd", "usd_per_bp"):
                result, unit = a.value / b.value, "bp"
            else:
                raise ValueError(f"a ratio of {a.unit} to {b.unit} is not meaningful here")
        else:  # percent_change
            if a.unit != b.unit:
                raise ValueError("percent_change needs values with the same unit")
            if a.value == 0:
                raise ValueError("cannot take a percent change from zero")
            result, unit = 100.0 * (b.value - a.value) / abs(a.value), "pct"
    out.value(result, unit, args.label, f"derive:{op}", inputs=list(args.operands))


HANDLERS = {
    "get_curve": _get_curve,
    "get_portfolio_summary": _get_portfolio_summary,
    "get_positions": _get_positions,
    "run_scenario": _run_scenario,
    "compare_hedges": _compare_hedges,
    "get_hedge": _get_hedge,
    "get_mbs_profile": _get_mbs_profile,
    "get_methodology": _get_methodology,
    "derive": _derive,
}


def run_tool(name: str, raw_args: dict[str, Any], ledger: Ledger, data: AgentData) -> dict[str, Any]:
    """Run a data tool. Returns the JSON the model sees; never raises for bad input."""
    if name not in HANDLERS:
        return {"error": f"unknown tool {name!r}"}
    try:
        args = ARG_MODELS[name].model_validate(raw_args)
    except ValidationError as e:
        return {"error": f"invalid arguments: {e.errors(include_url=False, include_input=False)}"}
    snapshot_values, snapshot_context, next_id = dict(ledger.values), list(ledger.context), ledger._next
    out = _Out(name, raw_args, ledger, data)
    try:
        HANDLERS[name](out, args, data)
    except (ValueError, KeyError, StopIteration) as e:
        ledger.values, ledger.context, ledger._next = snapshot_values, snapshot_context, next_id
        return {"error": str(e) or type(e).__name__}
    return out.result
