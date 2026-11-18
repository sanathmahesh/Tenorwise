"""POST /api/scenario: custom parallel or key-rate shock (PLAN.md section 8).

The function rebuilds the market from the snapshot's inputs.json and must give
exactly what the engine gives. Runs against the pinned fixture snapshot.
"""

import pytest
from fastapi.testclient import TestClient

from tenorwise.api.app import app
from tenorwise.curve.shocks import key_rate_shock, parallel_shock
from tenorwise.hedging.grid import grid_cells
from tenorwise.hedging.strategies import build_strategies
from tenorwise.paths import FIXTURES_DIR
from tenorwise.portfolio.positions import load_positions
from tenorwise.portfolio.valuation import build_market_context, value_portfolio
from tenorwise.scenarios.definitions import Scenario
from tenorwise.scenarios.revaluation import run_scenario
from tenorwise.snapshot.convert import scenario_response
from tenorwise.snapshot.inputs import MarketInputs
from tenorwise.snapshot.serialize import to_jsonable

SNAPSHOT = FIXTURES_DIR / "snapshot_v1"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(SNAPSHOT))
    return TestClient(app)


@pytest.fixture(scope="module")
def engine():
    inputs = MarketInputs.from_fixtures()
    ctx = build_market_context(inputs.par, inputs.mortgage)
    positions = load_positions()
    strategies = build_strategies(value_portfolio(positions, ctx), ctx)
    return inputs, ctx, positions, strategies


def expected(engine, scenario):
    inputs, ctx, positions, strategies = engine
    result = run_scenario(scenario, positions, ctx)
    return to_jsonable(scenario_response(result, grid_cells(strategies, result, ctx), inputs.par))


def test_custom_parallel_shift_equals_the_engine(client, engine):
    response = client.post("/api/scenario", json={"parallel_bp": 150})

    assert response.status_code == 200
    scenario = Scenario("custom", "Custom: +150 bp parallel", "Custom parallel shift of +150 bp.",
                        tuple(float(x) for x in parallel_shock(150.0)))
    assert response.json() == expected(engine, scenario)


def test_custom_key_rate_shock_equals_the_engine(client, engine):
    response = client.post("/api/scenario", json={"key_rate_bp": {"2": 10, "5": -20, "10": 30, "30": 0}})

    assert response.status_code == 200
    shock = key_rate_shock(2, 10.0) + key_rate_shock(5, -20.0) + key_rate_shock(10, 30.0) + key_rate_shock(30, 0.0)
    scenario = Scenario("custom", "Custom: key-rate shock", "Custom key-rate shock: 2y +10, 5y -20, 10y +30, 30y +0 bp.",
                        tuple(float(x) for x in shock))
    assert response.json() == expected(engine, scenario)


@pytest.mark.parametrize(
    "body",
    [
        {"parallel_bp": 301},
        {"parallel_bp": -300.5},
        {"key_rate_bp": {"2": 0, "5": 0, "10": -301, "30": 0}},
        {"key_rate_bp": {"2": 0, "5": 0, "10": 0}},
        {"parallel_bp": 10, "key_rate_bp": {"2": 0, "5": 0, "10": 0, "30": 0}},
        {},
        {"parallel_bp": "lots"},
    ],
    ids=["above-300", "below-300", "key-rate-out-of-range", "key-rate-missing-bucket", "both", "neither", "not-a-number"],
)
def test_rejects_out_of_range_or_malformed_input(client, body):
    assert client.post("/api/scenario", json=body).status_code == 422


def test_limits_are_inclusive(client):
    assert client.post("/api/scenario", json={"parallel_bp": -300}).status_code == 200


def test_response_carries_the_data_date_and_hedge_rows(client):
    body = client.post("/api/scenario", json={"parallel_bp": -50}).json()
    assert body["data_date"] == "2026-11-16"
    assert [r["strategy_id"] for r in body["grid"]] == ["unhedged", "dv01_50", "dv01_full", "key_rate"]
    assert body["scenario"]["floor_bound"] is False


def test_without_a_snapshot_the_scenario_endpoint_says_so(monkeypatch, tmp_path):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(tmp_path / "missing"))
    assert TestClient(app).post("/api/scenario", json={"parallel_bp": 10}).status_code == 503


def test_phase0_deploy_check_is_gone(client):
    assert client.get("/api/deploy-check").status_code == 404
