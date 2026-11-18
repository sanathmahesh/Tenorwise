"""Snapshot build (PLAN.md section 8, Phase 7).

Built from the pinned fixtures (Treasury curve, mortgage rate, 2022 replay).
"""

import json
from pathlib import Path

import pytest

from tenorwise.paths import FIXTURES_DIR
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context, value_portfolio
from tenorwise.snapshot.build import FUNCTION_ONLY_FILES, SNAPSHOT_FILES, build_snapshot
from tenorwise.snapshot.inputs import MarketInputs
from tenorwise.snapshot.models import MODELS

PINNED_SNAPSHOT_DIR = FIXTURES_DIR / "snapshot_v1"
FIXED = dict(build_time="2026-11-18T02:07:30Z", git_sha="fixture", llm_model=None)


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    root = tmp_path_factory.mktemp("snap")
    out = []
    for name in ("a", "b"):
        web, fn = root / name / "web", root / name / "fn"
        build_snapshot(MarketInputs.from_fixtures(), [web], [fn], **FIXED)
        out.append((web, fn))
    return out


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_writes_every_contract_file(builds):
    web, fn = builds[0]
    assert sorted(p.name for p in web.iterdir()) == sorted(SNAPSHOT_FILES)
    assert sorted(p.name for p in fn.iterdir()) == sorted(SNAPSHOT_FILES + FUNCTION_ONLY_FILES)
    assert set(SNAPSHOT_FILES) == {
        "meta.json", "curve.json", "portfolio.json", "mbs.json",
        "scenarios.json", "hedges.json", "methods.json", "evidence.json",
    }


def test_two_builds_from_the_same_fixture_are_byte_identical(builds):
    (web_a, fn_a), (web_b, fn_b) = builds
    for name in SNAPSHOT_FILES:
        assert (web_a / name).read_bytes() == (web_b / name).read_bytes(), name
        assert (web_a / name).read_bytes() == (fn_a / name).read_bytes(), name
    for name in FUNCTION_ONLY_FILES:
        assert (fn_a / name).read_bytes() == (fn_b / name).read_bytes(), name


def test_pinned_fixture_snapshot_matches_a_fresh_build(builds):
    web, fn = builds[0]
    for name in SNAPSHOT_FILES:
        assert (PINNED_SNAPSHOT_DIR / name).read_bytes() == (web / name).read_bytes(), name
    for name in FUNCTION_ONLY_FILES:
        assert (PINNED_SNAPSHOT_DIR / name).read_bytes() == (fn / name).read_bytes(), name


@pytest.mark.parametrize("name", list(MODELS))
def test_every_json_file_validates_against_its_schema(builds, name):
    web, fn = builds[0]
    path = (fn if name in FUNCTION_ONLY_FILES else web) / name
    MODELS[name].model_validate_json(path.read_text(encoding="utf-8"))


def test_serialization_is_sorted_and_has_no_negative_zero(builds):
    web, _ = builds[0]
    for name in SNAPSHOT_FILES:
        text = (web / name).read_text(encoding="utf-8")
        assert text == json.dumps(json.loads(text), sort_keys=True, indent=1, ensure_ascii=False) + "\n", name
        assert "-0.0," not in text and "-0.0\n" not in text and ": -0}" not in text, name


def test_market_data_date_is_in_every_file(builds):
    web, _ = builds[0]
    for name in SNAPSHOT_FILES:
        assert load(web / name)["data_date"] == "2026-11-16", name


def test_contents_match_the_engine_in_contract_units(builds):
    """Money in US dollars, rates in percent (PLAN.md section 8)."""
    web, _ = builds[0]
    inputs = MarketInputs.from_fixtures()
    ctx = build_market_context(inputs.par, inputs.mortgage)
    pv = value_portfolio(load_positions(), ctx)

    portfolio = load(web / "portfolio.json")
    assert portfolio["summary"]["market_value"] == pytest.approx(pv.summary.market_value * 1e6, rel=1e-9)
    assert portfolio["summary"]["dv01"] == pytest.approx(pv.summary.dv01 * 1e6, rel=1e-9)
    assert len(portfolio["positions"]) == 38
    first = portfolio["positions"][0]
    assert first["book_yield"] == pytest.approx(100 * pv.positions[0].position.book_yield, rel=1e-9)
    assert first["class"] in ("AFS", "HTM")

    curve = load(web / "curve.json")
    assert [p["par_yield"] for p in curve["points"]] == pytest.approx([100 * y for y in inputs.par.par_yields], rel=1e-9)

    scenarios = load(web / "scenarios.json")
    ids = [s["id"] for s in scenarios["scenarios"]]
    assert ids == ["base", "parallel_up_100", "parallel_down_100", "parallel_up_200", "parallel_down_200",
                   "bear_steepener", "bull_flattener", "replay_2022"]

    hedges = load(web / "hedges.json")
    assert [s["id"] for s in hedges["strategies"]] == ["unhedged", "dv01_50", "dv01_full", "key_rate"]
    assert len(hedges["grid"]) == 4 * len(ids)
    assert hedges["swap_spread_bp"] == 0.0


def test_stylized_and_proxy_labels_reach_the_api(builds):
    web, _ = builds[0]
    mbs = load(web / "mbs.json")
    assert mbs["stylized"] is True and "stylized" in mbs["stylized_note"].lower()
    for p in load(web / "portfolio.json")["positions"]:
        assert p["stylized"] == (p["sector"] == "agency_mbs")


def test_evidence_carries_the_measured_quantlib_report_and_no_unmeasured_figures(builds):
    web, _ = builds[0]
    evidence = load(web / "evidence.json")
    report = load(Path(__file__).resolve().parents[2] / "docs" / "evidence" / "quantlib_report.json")
    assert [q["measure"] for q in evidence["quantlib"]] == [m["measure"] for m in report["quantlib"]]
    assert evidence["models"] == [] and evidence["questions"] == []  # no eval summary passed: none published


def test_meta_lists_assumptions_and_fred_series(builds):
    web, _ = builds[0]
    meta = load(web / "meta.json")
    assert [a["id"] for a in meta["assumptions"]][:3] == ["A-01", "A-02", "A-03"]
    ids = {s["id"] for s in meta["fred_series"]}
    assert {"DGS1MO", "DGS10", "DGS30", "OBMMIC30YF"} <= ids


# ------------------------------------------------------------------ Phase 11 additions (owner-approved, D-076)


def test_sector_rows_split_market_value_by_accounting_class(builds):
    web, _ = builds[0]
    portfolio = load(web / "portfolio.json")
    for row in portfolio["by_sector"]:
        split = row["market_value_by_class"]
        assert set(split) == {"AFS", "HTM"}
        for klass in ("AFS", "HTM"):
            expected = sum(p["market_value"] for p in portfolio["positions"]
                           if p["sector"] == row["id"] and p["class"] == klass)
            assert split[klass] == pytest.approx(expected, rel=1e-9, abs=1e-3)
        assert split["AFS"] + split["HTM"] == pytest.approx(row["market_value"], rel=1e-9)


def test_mbs_profile_rows_carry_the_engines_refinancing_incentive(builds):
    web, _ = builds[0]
    mbs = load(web / "mbs.json")
    rows = {r["shift_bp"]: r for r in mbs["profile"]}
    # incentive (percentage points) = pool WAC minus the mortgage rate after the shift
    assert rows[0.0]["incentive_pct"] == pytest.approx(mbs["pool"]["wac"] - mbs["mortgage_rate"]["mortgage_rate"], abs=1e-6)
    for s, r in rows.items():
        assert r["incentive_pct"] == pytest.approx(rows[0.0]["incentive_pct"] - s / 100, abs=1e-6)
