"""Agent tools: schemas, argument validation, unique value IDs, derive (PLAN.md section 9).

Tools read the pinned fixture snapshot (data/fixtures/snapshot_v1).
"""

import json

import pytest

from tenorwise.agent.data import AgentData
from tenorwise.agent.ledger import Ledger
from tenorwise.agent.tools import DATA_TOOLS, run_tool, tool_specs
from tenorwise.paths import FIXTURES_DIR

SNAPSHOT = FIXTURES_DIR / "snapshot_v1"


@pytest.fixture
def data():
    return AgentData.load(SNAPSHOT)


@pytest.fixture
def ledger():
    return Ledger()


def walk(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)
    else:
        yield obj


@pytest.mark.parametrize("mode", ["ask", "commentary"])
def test_tool_schemas_are_valid_function_tools(mode):
    specs = tool_specs(mode)
    names = [s["function"]["name"] for s in specs]
    assert len(names) == len(set(names))
    expected = {"get_curve", "get_portfolio_summary", "get_positions", "run_scenario", "compare_hedges",
                "get_hedge", "get_mbs_profile", "get_methodology", "derive"}
    assert expected <= set(names)
    assert ("submit_answer" in names) == (mode == "ask")
    assert ("submit_commentary" in names) == (mode == "commentary")
    for spec in specs:
        assert spec["type"] == "function"
        params = spec["function"]["parameters"]
        assert params["type"] == "object"
        text = json.dumps(params)
        assert "$ref" not in text and "$defs" not in text  # fully inlined for OpenAI-compatible providers
        assert spec["function"]["description"]


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("run_scenario", {"parallel_bp": 999}),
        ("run_scenario", {}),
        ("run_scenario", {"scenario_id": "nope"}),
        ("get_hedge", {"strategy_id": "dv01_200"}),
        ("get_positions", {"sector": "equities"}),
        ("derive", {"operation": "sum", "operands": ["v1"], "label": "x"}),
        ("no_such_tool", {}),
    ],
)
def test_bad_arguments_return_an_error_to_the_model_not_an_exception(data, ledger, name, args):
    result = run_tool(name, args, ledger, data)
    assert "error" in result
    assert ledger.values == {}


@pytest.mark.parametrize("name", [t for t in DATA_TOOLS if t != "derive"])  # derive is tested below
def test_every_numeric_value_in_a_tool_result_has_a_unique_id(data, ledger, name):
    args = {
        "run_scenario": {"scenario_id": "parallel_up_100"},
        "compare_hedges": {"scenario_id": "bear_steepener"},
        "get_hedge": {"strategy_id": "key_rate"},
        "get_methodology": {"method_id": "dv01"},
        "get_positions": {"sector": "agency_mbs"},
    }.get(name, {})
    result = run_tool(name, args, ledger, data)
    assert "error" not in result, result
    ids = [v["id"] for v in result.get("values", [])]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(ledger.values)
    # No bare numbers anywhere: every figure travels as a display string under an ID.
    assert not any(isinstance(x, (int, float)) and not isinstance(x, bool) for x in walk(result)), result


def test_ids_stay_unique_across_tool_calls(data, ledger):
    a = run_tool("get_portfolio_summary", {}, ledger, data)
    b = run_tool("run_scenario", {"scenario_id": "replay_2022"}, ledger, data)
    ids = [v["id"] for v in a["values"] + b["values"]]
    assert len(ids) == len(set(ids)) == len(ledger.values)


def test_tool_values_equal_the_snapshot(data, ledger):
    result = run_tool("get_portfolio_summary", {}, ledger, data)
    mv = next(v for v in result["values"] if v["label"] == "Portfolio market value")
    assert ledger.values[mv["id"]].value == data.portfolio["summary"]["market_value"]
    assert ledger.values[mv["id"]].method == "portfolio_aggregate"


def test_custom_scenario_tool_equals_the_api(data, ledger, monkeypatch):
    from tenorwise.api.scenario import run_custom
    from tenorwise.snapshot.models import ScenarioRequest

    result = run_tool("run_scenario", {"parallel_bp": 150}, ledger, data)
    total = next(v for v in result["values"] if v["label"] == "Change in market value, total")
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(SNAPSHOT))
    api = run_custom(ScenarioRequest(parallel_bp=150))
    assert ledger.values[total["id"]].value == api["scenario"]["total"]["delta_mv"]
    assert any(c.value == 150 for c in ledger.context)  # tool arguments become context numbers


# ------------------------------------------------------------------ derive


@pytest.fixture
def seeded():
    led = Ledger()
    led.add(-230_800_000.0, "usd", "AFS change", tool="t", args={}, method="m")  # v1
    led.add(234_800_000.0, "usd", "Swap gain", tool="t", args={}, method="m")  # v2
    led.add(2_409_200.0, "usd_per_bp", "AFS DV01", tool="t", args={}, method="m")  # v3
    led.add(4.0, "years", "Duration", tool="t", args={}, method="m")  # v4
    return led


@pytest.mark.parametrize(
    ("operation", "operands", "value", "unit"),
    [
        ("sum", ["v1", "v2"], 4_000_000.0, "usd"),
        ("difference", ["v2", "v1"], 465_600_000.0, "usd"),
        ("ratio", ["v2", "v1"], 234.8 / -230.8, "number"),
        ("ratio", ["v1", "v3"], -230_800_000.0 / 2_409_200.0, "bp"),
        ("percent_change", ["v1", "v2"], 100 * (234.8 - (-230.8)) / 230.8, "pct"),
    ],
)
def test_derive_computes_correctly(data, seeded, operation, operands, value, unit):
    result = run_tool("derive", {"operation": operation, "operands": operands, "label": "x"}, seeded, data)
    assert "error" not in result, result
    new = seeded.values[result["values"][0]["id"]]
    assert new.value == pytest.approx(value, rel=1e-12)
    assert new.unit == unit
    assert new.inputs == operands
    assert new.method == f"derive:{operation}"


@pytest.mark.parametrize(
    ("operation", "operands"),
    [
        ("sum", ["v1", "v99"]),  # unknown operand
        ("sum", ["v1", "v4"]),  # unit mismatch
        ("difference", ["v1"]),  # wrong arity
        ("ratio", ["v1", "v4"]),  # meaningless units
    ],
)
def test_derive_rejects_unknown_operands_and_unit_mismatches(data, seeded, operation, operands):
    before = dict(seeded.values)
    result = run_tool("derive", {"operation": operation, "operands": operands, "label": "x"}, seeded, data)
    assert "error" in result
    assert seeded.values == before


def test_derive_rejects_division_by_zero(data):
    led = Ledger()
    led.add(5.0, "usd", "a", tool="t", args={}, method="m")
    led.add(0.0, "usd", "b", tool="t", args={}, method="m")
    assert "error" in run_tool("derive", {"operation": "ratio", "operands": ["v1", "v2"], "label": "x"}, led, data)
