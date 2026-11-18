"""Live smoke test against the real LLM provider. Skipped by default.

Run with:  TENORWISE_LIVE=1 uv run --env-file .env pytest tests/agent/test_live_smoke.py
Makes one real question (a few model calls; a few cents at most).
"""

import os

import pytest

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import run_agent
from tenorwise.agent.provider import provider_from_env
from tenorwise.paths import FIXTURES_DIR

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.environ.get("TENORWISE_LIVE") != "1", reason="live LLM test; set TENORWISE_LIVE=1 to run")
def test_one_real_question_is_answered_and_verified():
    provider = provider_from_env()
    assert provider is not None, "LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must be set"
    r = run_agent("ask", "What is the portfolio's total market value and DV01?", [], provider,
                  AgentData.load(FIXTURES_DIR / "snapshot_v1"))
    print(f"\nstatus={r.status} model={r.usage.model} tier={r.usage.served_tier} calls={r.usage.llm_calls} "
          f"tokens={r.usage.prompt_tokens}+{r.usage.completion_tokens} cost={r.usage.cost_usd} "
          f"upper_bound={r.usage.cost_is_upper_bound} latency_ms={r.usage.latency_ms}")
    print("answer:", r.answer_md)
    print("checks:", [(c.token, c.tag, c.passed, c.reason) for c in r.checks])
    print("trace:", [(t.tool, t.args) for t in r.trace], "error:", r.error)
    assert r.status in ("answered", "blocked"), r.status
    assert r.usage.llm_calls >= 1
    if r.status == "answered":
        assert all(c.passed for c in r.checks)
