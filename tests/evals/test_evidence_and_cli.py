"""Eval results reach evidence.json; known value coincidences are pinned; the run command's guards."""

import json
from datetime import date

import pytest

from tenorwise.agent.data import AgentData
from tenorwise.agent.ledger import Ledger
from tenorwise.agent.tools import SCENARIO_IDS, STRATEGY_IDS, run_tool
from tenorwise.evals.__main__ import refuse_reason
from tenorwise.evals.engine import EngineContext
from tenorwise.evals.estimate import estimate
from tenorwise.evals.grader import matches
from tenorwise.evals.oracle import oracle_provider
from tenorwise.evals.questions import QUESTIONS
from tenorwise.evals.report import write_report
from tenorwise.evals.runner import run_eval
from tenorwise.paths import FIXTURES_DIR
from tenorwise.snapshot.build import build_snapshot
from tenorwise.snapshot.inputs import MarketInputs
from tenorwise.snapshot.models import Evidence

EVAL_MODELS = ("zai-org/GLM-5.3", "deepseek-ai/DeepSeek-V4.1-Flash-1017", "moonshotai/Kimi-K3.1-Pro")


def test_eval_summary_is_published_in_evidence_json(tmp_path):
    raw = tmp_path / "raw"
    run_eval("oracle/fake", oracle_provider, repeats=1, out_dir=raw)
    summary = write_report(raw, tmp_path / "summary.json", tmp_path / "report.md")
    assert "oracle/fake" in (tmp_path / "report.md").read_text()

    web = tmp_path / "web"
    build_snapshot(MarketInputs.from_fixtures(), [web], [], "2026-11-18T00:00:00Z", "fixture", None,
                   eval_summary=tmp_path / "summary.json")
    evidence = Evidence.model_validate(json.loads((web / "evidence.json").read_text()))
    assert [m.id for m in evidence.models] == ["oracle/fake"]
    m = evidence.models[0]
    assert (m.accuracy, m.block_rate, m.verified_but_wrong_rate, m.runs) == (1.0, 0.0, 0.0, 1)
    assert m.latency_p50_ms == summary["models"][0]["latency_p50_ms"]
    assert len(evidence.questions) == 36
    assert all(q.results == {"oracle/fake": "pass"} for q in evidence.questions)


# ------------------------------------------------------------------ known coincidences

# Values a model could cite that also fall within 0.5% of a gold value. The grader
# matches values, not meaning, so these would pass (LIMITATIONS.md). "same" =
# equal by definition; "coincidence" = a different quantity that happens to be close.
KNOWN_COLLISIONS = {
    ("A1", "10-year swap fixed rate"): "same",  # swap spread is 0 (A-32), so the swap par rate equals the par yield
    ("B1", "Unhedged: net change in value (securities + swaps)"): "same",
    ("B1", "50% DV01 hedge: net change in value (securities + swaps)"): "coincidence",  # at +150 bp
    ("B2", "Change in market value, Available-for-sale"): "same",
    ("B2", "Unhedged: AOCI net of hedges"): "same",
    ("B3", "Change in market value, Held-to-maturity"): "same",
    ("B5", "Unhedged: net change in value (securities + swaps)"): "same",
    ("C2", "Key-rate-matched hedge: net change in value (securities + swaps)"): "coincidence",  # at -200 bp
    ("C3", "AGY-H1 market value"): "coincidence",
    ("D1", "AOCI impact (AFS change, pre-tax)"): "coincidence",  # at +150 bp
    ("D1", "Change in market value, Available-for-sale"): "coincidence",
    ("D1", "Unhedged: AOCI net of hedges"): "coincidence",
    ("E1", "ACM-H1 effective duration"): "coincidence",
    ("E1", "ACM-H1 modified duration (yield-based)"): "coincidence",
    ("E1", "AGY-A3 effective duration"): "coincidence",
    ("E1", "AGY-A3 modified duration (yield-based)"): "coincidence",
    ("E1", "MBS-A3 modified duration (yield-based)"): "coincidence",
}


def test_gold_value_coincidences_across_all_tool_outputs_are_known():
    data = AgentData.load(FIXTURES_DIR / "snapshot_v1")
    engine = EngineContext.from_fixtures()
    ledger = Ledger()
    calls = [("get_curve", {}), ("get_mbs_profile", {})]
    calls += [("get_portfolio_summary", {"group": g}) for g in ("total", "sector", "class")]
    calls += [("get_positions", {"position_id": p["id"]}) for p in data.portfolio["positions"]]
    calls += [(t, {"scenario_id": s}) for s in SCENARIO_IDS for t in ("run_scenario", "compare_hedges")]
    calls += [("get_hedge", {"strategy_id": s}) for s in STRATEGY_IDS]
    calls += [(t, {"parallel_bp": b}) for b in (50, 150) for t in ("run_scenario", "compare_hedges")]
    calls += [("run_scenario", {"key_rate_bp": {"2": 0, "5": 0, "10": 50, "30": 0}})]
    for name, args in calls:
        assert "error" not in run_tool(name, args, ledger, data), (name, args)

    found = set()
    for q in QUESTIONS:
        cited = {ref[1] for ref in q.cite}
        for g in q.gold(engine):
            for v in ledger.values.values():
                if matches(g, {"value": v.value, "unit": v.unit}) and v.label not in cited:
                    found.add((q.id, v.label))
    assert found == set(KNOWN_COLLISIONS)


# ------------------------------------------------------------------ run guards and estimate


PRICES = {"read_on": "2026-11-18", "usd_per_million_tokens": {m: {"asap": {}} for m in EVAL_MODELS}}
ENV = {"LLM_BASE_URL": "https://example.invalid/v1", "LLM_API_KEY": "k"}


def test_run_is_refused_without_todays_prices_or_a_known_model_or_credentials():
    today = date(2026, 11, 18)
    assert refuse_reason("zai-org/GLM-5.3", PRICES, today, ENV) is None
    assert "re-read" in refuse_reason("zai-org/GLM-5.3", PRICES, date(2026, 11, 19), ENV)
    assert "no list price" in refuse_reason("someone/else", PRICES, today, ENV)
    assert "LLM_API_KEY" in refuse_reason("zai-org/GLM-5.3", PRICES, today, {"LLM_BASE_URL": "x"})


def test_estimate_is_calibrated_to_the_measured_smoke_test():
    est = estimate(repeats=3)
    assert est["calibration"]["measured_prompt_tokens"] == 5129
    assert set(est["models"]) == set(EVAL_MODELS)
    for m in EVAL_MODELS:
        assert est["models"][m]["total_usd"] > 0
    assert est["questions"] == 36 and est["repeats"] == 3


@pytest.mark.parametrize("model", EVAL_MODELS)
def test_eval_models_have_list_prices(model):
    from tenorwise.agent.provider import PRICES_FILE

    prices = json.loads(PRICES_FILE.read_text())["usd_per_million_tokens"]
    assert {"asap", "balanced", "flex"} <= set(prices[model])


# ------------------------------------------------------------------ summary counts and the zero-failure bound


def test_summary_carries_counts_and_an_exact_upper_bound_on_verified_but_wrong(tmp_path):
    from tenorwise.evals.report import summarize

    path = run_eval("oracle/fake", oracle_provider, repeats=1, out_dir=tmp_path)
    m = summarize([path])["models"][0]
    assert (m["passes"], m["blocked"], m["repairs"], m["errors"], m["verified_runs"], m["verified_but_wrong"]) == (36, 0, 0, 0, 36, 0)
    # zero wrong in n verified answers: the rate p with (1 - p)^n = 0.05 (one-sided 95%)
    assert m["verified_but_wrong_upper_95"] == pytest.approx(1 - 0.05 ** (1 / 36), rel=1e-9)
