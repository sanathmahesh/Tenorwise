"""Build-time pre-compute: run the engine once and write the static JSON snapshot.

Files (PLAN.md section 8) go to the web folder (served as static files) and the
function folder (read by the API). The function folder also gets inputs.json:
the full-precision engine inputs the API needs to recompute custom scenarios.
Serialization is deterministic (serialize.py).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from tenorwise.analytics.mbs_profile import (
    current_coupon_pool,
    matching_treasury,
    mbs_profile,
    s_curve,
    treasury_comparison,
)
from tenorwise.curve.fred import PAR_SERIES
from tenorwise.curve.mortgage_spread import ATTRIBUTION, MORTGAGE_RATE_SERIES
from tenorwise.hedging.grid import grid_cells
from tenorwise.hedging.strategies import afs_risk, build_strategies
from tenorwise.instruments.mbs import DEFAULT_MODEL, STYLIZED, STYLIZED_NOTE
from tenorwise.paths import REPO_ROOT
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.sources import load_bny_source
from tenorwise.portfolio.valuation import build_market_context, value_portfolio
from tenorwise.scenarios.definitions import Scenario, preset_scenarios
from tenorwise.scenarios.replay import REPLAY_END, REPLAY_START
from tenorwise.scenarios.revaluation import run_scenario
from tenorwise.snapshot import convert as cv
from tenorwise.snapshot import models as m
from tenorwise.snapshot.inputs import MarketInputs
from tenorwise.snapshot.methods import METHODS
from tenorwise.snapshot.serialize import dumps, dumps_exact, to_jsonable
from tenorwise.snapshot.store import DEFAULT_SNAPSHOT_DIR

WEB_OUT_DIR = REPO_ROOT / "web" / "public" / "data" / "v1"
FUNCTION_OUT_DIR = DEFAULT_SNAPSHOT_DIR
SNAPSHOT_FILES = [
    "meta.json", "curve.json", "portfolio.json", "mbs.json",
    "scenarios.json", "hedges.json", "methods.json", "evidence.json",
]
FUNCTION_ONLY_FILES = ["inputs.json"]
SWAP_SPREAD = 0.0  # decimal; swap curve = Treasury zero curve + this (A-32)
QUANTLIB_REPORT = REPO_ROOT / "docs" / "evidence" / "quantlib_report.json"
EVAL_SUMMARY = REPO_ROOT / "docs" / "evidence" / "evals" / "summary.json"  # written by python -m tenorwise.evals report
ASSUMPTIONS_MD = REPO_ROOT / "ASSUMPTIONS.md"

DGS_TITLES = {
    "DGS1MO": "1-Month", "DGS3MO": "3-Month", "DGS6MO": "6-Month", "DGS1": "1-Year", "DGS2": "2-Year",
    "DGS3": "3-Year", "DGS5": "5-Year", "DGS7": "7-Year", "DGS10": "10-Year", "DGS20": "20-Year", "DGS30": "30-Year",
}


def base_scenario(n_tenors: int) -> Scenario:
    return Scenario(
        "base", "Base (no shock)",
        "Today's curve with no shock: the starting point for carry and the cost of hedges.",
        (0.0,) * n_tenors,
    )


def parse_assumptions(path: Path = ASSUMPTIONS_MD) -> list[m.AssumptionItem]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| A-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) != 5:
            raise ValueError(f"cannot parse ASSUMPTIONS.md row: {line[:60]}")
        items.append(m.AssumptionItem(id=cells[0], text=cells[1], where=cells[2], effect=cells[3], phase=int(cells[4])))
    return items


def fred_series(inputs: MarketInputs) -> list[m.FredSeries]:
    out = [
        m.FredSeries(
            id=sid,
            title=f"Market Yield on U.S. Treasury Securities at {DGS_TITLES[sid]} Constant Maturity",
            use="Treasury par yield (curve), and the 2022 replay",
            observation_dates=[inputs.par.data_date.isoformat(), REPLAY_START.isoformat(), REPLAY_END.isoformat()],
        )
        for sid, _ in PAR_SERIES
    ]
    out.append(
        m.FredSeries(
            id=MORTGAGE_RATE_SERIES,
            title="30-Year Fixed Rate Conforming Mortgage Index (Optimal Blue)",
            use="Mortgage rate, for the mortgage spread over DGS10",
            observation_dates=[inputs.mortgage.date.isoformat()],
        )
    )
    return out


def eval_evidence(summary_path: Path | None) -> tuple[list[m.EvidenceModel], list[m.EvidenceQuestion]]:
    """evidence.json's models[] and questions[] from the eval summary (Phase 9); empty if there is none.

    accuracy: mean over repeats (fraction); block_rate: after the repair attempt;
    cost_per_question_usd: mean at list prices; runs: number of repeats.
    The summary also holds the ranges and the before-repair block rate (docs/evidence/evals/report.md).
    """
    if summary_path is None or not Path(summary_path).exists():
        return [], []
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    models = [
        m.EvidenceModel(
            id=x["id"], accuracy=x["accuracy"], block_rate=x["block_rate"],
            verified_but_wrong_rate=x["verified_but_wrong_rate"], latency_p50_ms=x["latency_p50_ms"],
            latency_p95_ms=x["latency_p95_ms"], cost_per_question_usd=x["cost_per_question_usd"] or 0.0, runs=x["runs"],
        )
        for x in summary["models"]
    ]
    questions = [
        m.EvidenceQuestion(id=q["id"], category=q["category"], text=q["text"], results=q["results"])
        for q in summary["questions"]
    ]
    return models, questions


def compute_snapshot(
    inputs: MarketInputs, build_time: str, git_sha: str | None, llm_model: str | None,
    eval_summary: Path | None = None,
) -> dict[str, str]:
    """Run the engine once; return {file name: JSON text}.

    eval_summary: the eval summary to publish in evidence.json. The pinned test
    snapshot is built without one, so rerunning evals never changes it.
    """
    data_date = inputs.par.data_date.isoformat()
    ctx = build_market_context(inputs.par, inputs.mortgage)
    positions = load_positions()
    pv = value_portfolio(positions, ctx)

    scenarios = [base_scenario(len(inputs.par.tenor_months))] + preset_scenarios(inputs.replay_shock_bp)
    results = [run_scenario(s, positions, ctx) for s in scenarios]
    strategies = build_strategies(pv, ctx, swap_spread=SWAP_SPREAD)
    cells = [c for r in results for c in grid_cells(strategies, r, ctx)]

    # mbs.json: the stylized current-coupon pool (D-033)
    mortgage_spread = inputs.mortgage.spread
    pool = current_coupon_pool(ctx.base, mortgage_spread)
    discount = ctx.sector_spreads["agency_mbs"]
    profile = mbs_profile(pool, ctx.par, mortgage_spread, discount)
    base_row = next(r for r in profile if r.shift_bp == 0)
    tsy = matching_treasury(ctx.par, base_row.eff_duration)

    cite = load_bny_source()["citation"]
    report = json.loads(QUANTLIB_REPORT.read_text(encoding="utf-8"))
    eval_models, eval_questions = eval_evidence(eval_summary)

    models: dict[str, m.Contract] = {
        "meta.json": m.Meta(
            data_date=data_date, build_time=build_time, git_sha=git_sha,
            fred_series=fred_series(inputs), llm_model=llm_model, assumptions=parse_assumptions(),
        ),
        "curve.json": m.Curve(data_date=data_date, points=cv.curve_points(ctx.base)),
        "portfolio.json": cv.portfolio_model(
            pv, data_date,
            m.Source(
                text=(
                    f"Mix based on {cite['company']}, Form {cite['form']} for the period ended {cite['period_ended']} "
                    f"(filed {cite['filing_date']}), Note 2, Investment securities, printed pages 52 and 55. "
                    "Positions are design choices sized from BNY's mix, not BNY's holdings."
                ),
                url=cite["pdf_url"],
            ),
        ),
        "mbs.json": m.Mbs(
            data_date=data_date,
            stylized=STYLIZED,
            stylized_note=STYLIZED_NOTE,
            pool=m.MbsPool(
                wac=cv.PCT * pool.wac, net_coupon=cv.PCT * pool.net_coupon, age_months=pool.age_months,
                remaining_months=pool.remaining_term_months, discount_spread_bp=1e4 * discount,
            ),
            mortgage_rate=m.MortgageRate(
                date=inputs.mortgage.date.isoformat(), mortgage_rate=cv.PCT * inputs.mortgage.mortgage_rate,
                ten_year_yield=cv.PCT * inputs.mortgage.ten_year_yield, spread=cv.PCT * mortgage_spread,
                series=MORTGAGE_RATE_SERIES, attribution=ATTRIBUTION,
            ),
            prepayment_model=m.PrepaymentParameters(
                cpr_min=cv.PCT * DEFAULT_MODEL.cpr_min, cpr_max=cv.PCT * DEFAULT_MODEL.cpr_max,
                k=DEFAULT_MODEL.k, x0=DEFAULT_MODEL.x0, ramp_months=DEFAULT_MODEL.ramp_months,
            ),
            comparison_treasury_bond=m.TreasuryBond(coupon=cv.PCT * tsy.coupon, maturity_years=tsy.maturity_months / 12.0),
            profile=[
                m.MbsProfileRow(
                    shift_bp=r.shift_bp, price=r.price, eff_duration=r.eff_duration,
                    avg_life_years=r.avg_life_years, cpr=cv.PCT * r.cpr, eff_convexity=r.eff_convexity,
                    incentive_pct=r.incentive_pct,
                )
                for r in profile
            ],
            comparison_treasury=[m.PriceRow(shift_bp=b, price=p) for b, p in treasury_comparison(tsy, ctx.par)],
            s_curve=[m.SCurveRow(incentive_pct=x, cpr=cv.PCT * c) for x, c in s_curve()],
        ),
        "scenarios.json": m.Scenarios(
            data_date=data_date,
            base_market_value=cv.USD * pv.summary.market_value,
            scenarios=[cv.scenario_entry(r) for r in results],
        ),
        "hedges.json": m.Hedges(
            data_date=data_date,
            swap_spread_bp=1e4 * SWAP_SPREAD,
            hedged_book="AFS",
            afs_dv01=cv.USD * afs_risk(pv).dv01,
            strategies=[cv.strategy_row(s) for s in strategies],
            grid=[cv.grid_row(c) for c in cells],
        ),
        "methods.json": m.Methods(data_date=data_date, methods={k: m.Method(**v) for k, v in METHODS.items()}),
        "evidence.json": m.Evidence(
            data_date=data_date,
            models=eval_models,
            questions=eval_questions,
            quantlib=[
                m.QuantlibRow(measure=q["measure"], instruments=q["instruments"], max_abs_diff=q["max_abs_diff"], unit=q["unit"])
                for q in report["quantlib"]
            ],
            quantlib_report_generated_at=report["generated_at"],
        ),
    }
    inputs_file = m.InputsFile(
        data_date=data_date,
        par_tenor_months=list(inputs.par.tenor_months),
        par_yields=list(inputs.par.par_yields),
        mortgage=m.StoredMortgage(
            date=inputs.mortgage.date.isoformat(), mortgage_rate=inputs.mortgage.mortgage_rate,
            ten_year_yield=inputs.mortgage.ten_year_yield, spread=inputs.mortgage.spread,
        ),
        swap_spread=SWAP_SPREAD,
        strategies=[
            m.StoredStrategy(
                id=st.id, name=st.name,
                swaps=[
                    m.StoredSwap(tenor_months=s.tenor_months, notional_musd=s.notional, fixed_rate=s.fixed_rate, swap_spread=s.swap_spread)
                    for s in st.swaps
                ],
            )
            for st in strategies
        ],
    )
    files = {name: dumps(to_jsonable(model)) for name, model in models.items()}
    files["inputs.json"] = dumps_exact(inputs_file)
    return files


def _write(directory: Path, files: dict[str, str], names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.json"):
        if stale.name not in names:
            stale.unlink()  # e.g. Phase 0's build_check.json
    for name in names:
        (directory / name).write_text(files[name], encoding="utf-8")


def build_snapshot(
    inputs: MarketInputs,
    web_dirs: Iterable[Path],
    function_dirs: Iterable[Path],
    build_time: str,
    git_sha: str | None,
    llm_model: str | None,
    eval_summary: Path | None = None,
) -> dict[str, str]:
    files = compute_snapshot(inputs, build_time, git_sha, llm_model, eval_summary)
    for d in web_dirs:
        _write(Path(d), files, SNAPSHOT_FILES)
    for d in function_dirs:
        _write(Path(d), files, SNAPSHOT_FILES + FUNCTION_ONLY_FILES)
    return files
