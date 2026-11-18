"""AI endpoints: rate limits, refusal when Redis is down, logging (PLAN.md section 9).

Provider and Redis are injected as fakes through FastAPI dependency overrides.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from tenorwise.agent.provider import FakeProvider, tool_response
from tenorwise.api import agent_routes
from tenorwise.api.app import app
from tenorwise.api.ratelimit import FakeRedis, Limiter, RedisUnavailable, ip_key
from tenorwise.paths import FIXTURES_DIR

SNAPSHOT = FIXTURES_DIR / "snapshot_v1"
QUESTION = "What is the portfolio's market value right now?"


def decline():
    return tool_response("submit_answer", {"status": "cannot_answer", "answer_md": "No numbers here."})


class DownRedis:
    def incr_with_expiry(self, key, ttl_s):
        raise RedisUnavailable("connection refused")


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(SNAPSHOT))
    state = {"redis": FakeRedis(), "per_ip": 2, "global": 3, "provider": FakeProvider([decline() for _ in range(10)])}

    app.dependency_overrides[agent_routes.get_provider] = lambda: state["provider"]
    app.dependency_overrides[agent_routes.get_limiter] = lambda: Limiter(
        state["redis"], salt="test-salt", per_ip_per_day=state["per_ip"], global_per_day=state["global"]
    )
    yield state
    app.dependency_overrides.clear()


def ask(client, ip, question=QUESTION):
    return client.post("/api/agent/ask", json={"question": question, "history": []}, headers={"x-forwarded-for": ip})


def test_answers_within_limits(setup):
    r = ask(TestClient(app), "203.0.113.1")
    assert r.status_code == 200 and r.json()["status"] == "cannot_answer"
    assert r.headers.get("x-request-id")


def test_per_ip_daily_cap(setup):
    client = TestClient(app)
    assert ask(client, "203.0.113.1").status_code == 200
    assert ask(client, "203.0.113.1").status_code == 200
    third = ask(client, "203.0.113.1")
    assert third.status_code == 429 and "per-IP" in third.json()["detail"]
    assert ask(client, "203.0.113.2").status_code == 200  # another IP still allowed


def test_global_daily_cap(setup):
    client = TestClient(app)
    for ip in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
        assert ask(client, ip).status_code == 200
    fourth = ask(client, "198.51.100.4")
    assert fourth.status_code == 429 and "global" in fourth.json()["detail"]


def test_ips_are_stored_only_as_salted_hashes(setup):
    ask(TestClient(app), "203.0.113.9")
    keys = list(setup["redis"].store)
    assert not any("203.0.113.9" in k for k in keys)
    assert any(ip_key("203.0.113.9", "test-salt") in k for k in keys)


def test_refuses_when_redis_is_down_without_calling_the_model(setup):
    setup["redis"] = DownRedis()
    r = ask(TestClient(app), "203.0.113.1")
    assert r.status_code == 503
    assert setup["provider"].calls == []  # the model was never called


def test_refuses_when_rate_limiting_is_not_configured(monkeypatch):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(SNAPSHOT))
    for var in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "RATE_LIMIT_BACKEND"):
        monkeypatch.delenv(var, raising=False)
    r = ask(TestClient(app), "203.0.113.1")
    assert r.status_code == 503


def test_memory_backend_is_refused_on_vercel(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RedisUnavailable):
        agent_routes.limiter_from_env()


def test_question_length_and_history_are_validated(setup):
    client = TestClient(app)
    assert ask(client, "203.0.113.1", question="x" * 1001).status_code == 422
    assert ask(client, "203.0.113.1", question="").status_code == 422


def test_logs_have_request_metadata_but_never_the_question(setup, caplog):
    with caplog.at_level(logging.INFO, logger="tenorwise.agent"):
        ask(TestClient(app), "203.0.113.1")
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "request_id" in text and "status" in text and "llm_calls" in text
    assert QUESTION not in text and "203.0.113.1" not in text


def test_commentary_endpoint(setup):
    r = TestClient(app).post("/api/agent/commentary", json={}, headers={"x-forwarded-for": "203.0.113.5"})
    assert r.status_code == 200
    assert r.json()["notice"] == "Draft, requires human review"


def test_a_global_cap_of_zero_turns_the_ai_endpoints_off_and_leaves_the_rest_working(setup):
    """The rollout plan's kill switch: AI_LIMIT_GLOBAL_PER_DAY=0."""
    setup["global"] = 0
    client = TestClient(app)
    r = ask(client, "192.0.2.1")
    assert r.status_code == 429
    assert setup["provider"].calls == []  # the model was never called
    assert client.post("/api/scenario", json={"parallel_bp": 100}).status_code == 200
