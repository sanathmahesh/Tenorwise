"""The live smoke script (PLAN.md Phase 12): health, data date, one AI question, and a 429
once the limit is passed. Tested here against the real app in-process, with a scripted
model and a fake Redis, so it costs nothing."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from tenorwise.agent.provider import FakeProvider, tool_response
from tenorwise.api import agent_routes
from tenorwise.api.app import app
from tenorwise.api.ratelimit import FakeRedis, Limiter
from tenorwise.paths import FIXTURES_DIR

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = FIXTURES_DIR / "snapshot_v1"
spec = importlib.util.spec_from_file_location("smoke_live", REPO / "scripts" / "smoke_live.py")
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke  # dataclasses need the module registered
spec.loader.exec_module(smoke)


def _answer(messages):
    for m in reversed(messages):
        if m["role"] == "tool":
            v = {x["label"]: x for x in json.loads(m["content"]).get("values", [])}["Portfolio market value"]
            return tool_response("submit_answer", {"status": "answered", "answer_md": f"It is worth {v['display']}[[{v['id']}]]."})
    raise AssertionError("no tool result")


def _decline():
    return tool_response("submit_answer", {"status": "cannot_answer", "answer_md": "Tenorwise cannot forecast."})


@pytest.fixture
def deployment(monkeypatch):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(SNAPSHOT))
    monkeypatch.setenv("LLM_MODEL", "zai-org/GLM-5.3")
    state = {"per_ip": 3}
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), _answer] + [_decline() for _ in range(20)])
    app.dependency_overrides[agent_routes.get_provider] = lambda: provider
    redis = FakeRedis()
    app.dependency_overrides[agent_routes.get_limiter] = lambda: Limiter(redis, salt="s", per_ip_per_day=state["per_ip"], global_per_day=100)
    yield state
    app.dependency_overrides.clear()


def site(meta_text: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/data/v1/meta.json":
            return httpx.Response(200, text=meta_text, headers={"content-type": "application/json"})
        if request.url.path == "/":
            return httpx.Response(200, text="<!doctype html><title>Tenorwise</title><div id=root></div>")
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://site")


META = (SNAPSHOT / "meta.json").read_text()


def test_smoke_passes_against_a_healthy_deployment(deployment):
    result = smoke.run_smoke(TestClient(app), site(META), today=date(2026, 11, 18), max_ai=6)
    failed = [c for c in result.checks if not c.passed]
    assert failed == []
    assert [c.name for c in result.checks] == [
        "health", "site serves the app", "data date matches", "data date is recent", "AI question answered and verified",
        "429 once the per-IP limit is passed",
    ]
    assert result.ai_requests == 4  # 3 allowed by the cap, then the 429


def test_smoke_fails_when_the_limit_is_never_reached(deployment):
    deployment["per_ip"] = 50
    result = smoke.run_smoke(TestClient(app), site(META), today=date(2026, 11, 18), max_ai=3)
    check = next(c for c in result.checks if c.name == "429 once the per-IP limit is passed")
    assert not check.passed and result.ai_requests == 3


def test_smoke_fails_on_stale_data(deployment):
    result = smoke.run_smoke(TestClient(app), site(META), today=date(2026, 12, 1), max_ai=6)
    assert not next(c for c in result.checks if c.name == "data date is recent").passed


def test_smoke_fails_when_the_static_data_disagrees_with_the_api(deployment):
    other = json.loads(META)
    other["data_date"] = "2026-11-13"
    result = smoke.run_smoke(TestClient(app), site(json.dumps(other)), today=date(2026, 11, 18), max_ai=6)
    assert not next(c for c in result.checks if c.name == "data date matches").passed


def test_a_429_from_in_front_of_the_app_is_not_mistaken_for_the_daily_cap():
    firewall = httpx.Response(429, text="<html>Too Many Requests</html>")
    app_cap = httpx.Response(429, json={"detail": "daily per-IP limit reached"})
    assert smoke.limit_source(firewall) == "firewall"
    assert smoke.limit_source(app_cap) == "app"
