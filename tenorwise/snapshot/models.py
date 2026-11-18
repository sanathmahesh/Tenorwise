"""The interface contract (PLAN.md section 8) as pydantic models.

Field names are the contract; the interface is designed against them. Units:
money in US dollars, DV01 in US dollars per basis point, rates and
percentages in percent, durations in years, shocks in basis points.
Additive fields beyond the plan's list are marked "added".

Every model forbids unknown fields, so a stray or misspelt key fails validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ------------------------------------------------------------------ shared


class KeyRateDV01(Contract):
    """Key-rate DV01 in US dollars per bp, keyed by bucket in years ("2", "5", "10", "30")."""

    y2: float = Field(alias="2")
    y5: float = Field(alias="5")
    y10: float = Field(alias="10")
    y30: float = Field(alias="30")


class CurvePoint(Contract):
    tenor_years: float
    par_yield: float = Field(description="percent, semiannual bond-equivalent")
    zero_rate: float = Field(description="percent, continuously compounded")
    discount_factor: float


# ------------------------------------------------------------------ meta.json


class FredSeries(Contract):
    id: str
    title: str
    use: str
    observation_dates: list[str]


class AssumptionItem(Contract):
    id: str
    text: str
    where: str
    effect: str
    phase: int


class Meta(Contract):
    data_date: str
    build_time: str
    git_sha: str | None
    fred_series: list[FredSeries]
    llm_model: str | None
    assumptions: list[AssumptionItem]


# ------------------------------------------------------------------ curve.json


class Curve(Contract):
    data_date: str
    points: list[CurvePoint]


# ------------------------------------------------------------------ portfolio.json


class RiskFields(Contract):
    market_value: float
    amortized_cost: float
    unrealized: float
    eff_duration: float
    convexity: float = Field(description="effective (curve-based) convexity")
    dv01: float
    key_rate_dv01: KeyRateDV01


class PortfolioSummary(RiskFields):
    pass


class GroupRow(RiskFields):
    id: str = Field(description="added: sector or class identifier")
    name: str = Field(description="added: display name")
    weight: float = Field(description="percent of total amortized cost")


class ClassSplit(Contract):
    """Market value in US dollars by accounting class."""

    afs: float = Field(alias="AFS")
    htm: float = Field(alias="HTM")


class SectorRow(GroupRow):
    market_value_by_class: ClassSplit = Field(
        description="added: market value of the sector's AFS and HTM positions (US dollars)"
    )


class PositionRow(Contract):
    id: str
    name: str
    sector: str
    klass: Literal["AFS", "HTM"] = Field(alias="class")
    face: float
    coupon: float = Field(description="percent; for mortgage pools, the net coupon")
    maturity_years: float
    book_yield: float = Field(description="percent")
    price: float = Field(description="per 100 of face")
    market_value: float
    amortized_cost: float
    unrealized: float
    eff_duration: float
    mod_duration: float = Field(description="yield-based")
    convexity: float = Field(description="effective (curve-based)")
    dv01: float
    key_rate_dv01: KeyRateDV01
    stylized: bool = Field(description="added: true for stylized agency mortgage pools")
    proxy_for: str | None = Field(description="added: BNY line an IG-corporate proxy stands in for")


class Source(Contract):
    text: str
    url: str


class Portfolio(Contract):
    data_date: str
    summary: PortfolioSummary
    by_sector: list[SectorRow]
    by_class: list[GroupRow]
    positions: list[PositionRow]
    source: Source


# ------------------------------------------------------------------ mbs.json


class MbsProfileRow(Contract):
    shift_bp: float
    price: float
    eff_duration: float
    avg_life_years: float
    cpr: float = Field(description="percent, first projected month")
    eff_convexity: float = Field(description="added")
    incentive_pct: float = Field(
        description="added: refinancing incentive in percentage points, pool WAC minus the mortgage rate after the shift"
    )


class PriceRow(Contract):
    shift_bp: float
    price: float


class SCurveRow(Contract):
    incentive_pct: float
    cpr: float = Field(description="percent, seasoned")


class MbsPool(Contract):
    wac: float
    net_coupon: float
    age_months: int
    remaining_months: int
    discount_spread_bp: float


class MortgageRate(Contract):
    date: str
    mortgage_rate: float
    ten_year_yield: float
    spread: float
    series: str
    attribution: str


class PrepaymentParameters(Contract):
    cpr_min: float
    cpr_max: float
    k: float
    x0: float
    ramp_months: int


class TreasuryBond(Contract):
    coupon: float
    maturity_years: float


class Mbs(Contract):
    data_date: str
    stylized: bool
    stylized_note: str
    pool: MbsPool
    mortgage_rate: MortgageRate
    prepayment_model: PrepaymentParameters
    comparison_treasury_bond: TreasuryBond
    profile: list[MbsProfileRow]
    comparison_treasury: list[PriceRow]
    s_curve: list[SCurveRow]


# ------------------------------------------------------------------ scenarios.json


class ShockPoint(Contract):
    tenor_years: float
    shock_bp: float


class ScenarioTotals(Contract):
    delta_mv: float
    delta_mv_pct: float = Field(description="percent of base market value")
    aoci_impact: float
    htm_unrecognized: float
    carry_12m: float


class ScenarioGroup(ScenarioTotals):
    id: str
    name: str


class ScenarioEntry(Contract):
    id: str
    name: str
    description: str
    shock_bp_by_tenor: list[ShockPoint]
    total: ScenarioTotals
    by_sector: list[ScenarioGroup]
    by_class: list[ScenarioGroup]
    shocked_curve: list[CurvePoint]
    floor_bound: bool = Field(description="added: shocked par yields hit the 0% floor")
    floored_tenor_years: list[float] = Field(description="added")


class Scenarios(Contract):
    data_date: str
    base_market_value: float = Field(description="added")
    scenarios: list[ScenarioEntry]


# ------------------------------------------------------------------ hedges.json


class SwapRow(Contract):
    tenor_years: float
    notional: float
    fixed_rate: float = Field(description="percent")
    dv01: float = Field(description="US dollars per bp; negative for pay-fixed")


class StrategyRow(Contract):
    id: str
    name: str
    swaps: list[SwapRow]
    key_rate_dv01_after: KeyRateDV01
    dv01_after: float = Field(description="added: AFS + swaps")


class GridRow(Contract):
    strategy_id: str
    scenario_id: str
    securities_delta_mv: float
    swap_pnl: float
    net_delta_mv: float
    aoci_net: float
    loss_avoided: float
    carry_given_up: float
    net_carry: float


class Hedges(Contract):
    data_date: str
    swap_spread_bp: float = Field(description="added: swap curve = Treasury zero curve + this spread")
    hedged_book: Literal["AFS"] = Field(description="added")
    afs_dv01: float = Field(description="added")
    strategies: list[StrategyRow]
    grid: list[GridRow]


# ------------------------------------------------------------------ methods.json


class Method(Contract):
    name: str
    plain_english: str
    formula: str
    notes_anchor: str


class Methods(Contract):
    data_date: str
    methods: dict[str, Method]


# ------------------------------------------------------------------ evidence.json


class EvidenceModel(Contract):
    id: str
    accuracy: float
    block_rate: float
    verified_but_wrong_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    cost_per_question_usd: float
    runs: int


class EvidenceQuestion(Contract):
    id: str
    category: str
    text: str
    results: dict[str, Literal["pass", "fail", "blocked"]]


class QuantlibRow(Contract):
    measure: str
    instruments: int
    max_abs_diff: float
    unit: str


class Evidence(Contract):
    data_date: str
    models: list[EvidenceModel]
    questions: list[EvidenceQuestion]
    quantlib: list[QuantlibRow]
    quantlib_report_generated_at: str = Field(description="added")


# ------------------------------------------------------------------ inputs.json (function only)


class StoredSwap(Contract):
    tenor_months: int
    notional_musd: float
    fixed_rate: float  # decimal
    swap_spread: float  # decimal


class StoredStrategy(Contract):
    id: str
    name: str
    swaps: list[StoredSwap]


class StoredMortgage(Contract):
    date: str
    mortgage_rate: float
    ten_year_yield: float
    spread: float


class InputsFile(Contract):
    """Full-precision engine inputs for the API function. Not served to the browser."""

    data_date: str
    par_tenor_months: list[int]
    par_yields: list[float]  # decimal
    mortgage: StoredMortgage
    swap_spread: float  # decimal
    strategies: list[StoredStrategy]


# ------------------------------------------------------------------ API


class HealthResponse(Contract):
    status: Literal["ok", "no_snapshot"]
    data_date: str | None
    build_time: str | None
    git_sha: str | None
    model_id: str | None


class KeyRateShockInput(Contract):
    """Shock in bp at each key-rate tent, -300 to +300 each."""

    y2: float = Field(alias="2", ge=-300, le=300)
    y5: float = Field(alias="5", ge=-300, le=300)
    y10: float = Field(alias="10", ge=-300, le=300)
    y30: float = Field(alias="30", ge=-300, le=300)


class ScenarioRequest(Contract):
    """Exactly one of: a parallel shift, or key-rate shocks."""

    parallel_bp: float | None = Field(default=None, ge=-300, le=300)
    key_rate_bp: KeyRateShockInput | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> ScenarioRequest:
        if (self.parallel_bp is None) == (self.key_rate_bp is None):
            raise ValueError("give exactly one of parallel_bp or key_rate_bp")
        return self


class ScenarioResponse(Contract):
    data_date: str
    scenario: ScenarioEntry
    grid: list[GridRow]


MODELS: dict[str, type[Contract]] = {
    "meta.json": Meta,
    "curve.json": Curve,
    "portfolio.json": Portfolio,
    "mbs.json": Mbs,
    "scenarios.json": Scenarios,
    "hedges.json": Hedges,
    "methods.json": Methods,
    "evidence.json": Evidence,
    "inputs.json": InputsFile,
}
