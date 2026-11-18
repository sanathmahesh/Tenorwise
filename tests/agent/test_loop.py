"""Agent loop with a scripted provider (PLAN.md section 9). No network.

A script step is either a fixed ProviderResponse, an exception to raise, or a
function of the messages so far (so it can read value IDs from tool results).
"""

import json

import pytest

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import MAX_MODEL_CALLS, MAX_QUESTION_CHARS, REVIEW_NOTICE, run_agent
from tenorwise.agent.provider import FakeProvider, ProviderError, text_response, tool_response
from tenorwise.paths import FIXTURES_DIR

SNAPSHOT = FIXTURES_DIR / "snapshot_v1"
HEADINGS = ["Positioning", "Rate sensitivity", "Scenario results", "Hedging trade-off", "Caveats"]


@pytest.fixture
def data():
    return AgentData.load(SNAPSHOT)


def last_values(messages):
    for m in reversed(messages):
        if m["role"] == "tool":
            body = json.loads(m["content"])
            if "values" in body:
                return {v["label"]: v for v in body["values"]}
    raise AssertionError("no tool result with values")


def answer_with(label, render=lambda v: f"{v['display']}[[{v['id']}]]", status="answered"):
    def step(messages):
        v = last_values(messages)[label]
        return tool_response("submit_answer", {"status": status, "answer_md": f"The figure is {render(v)}."})
    return step


MV = "Portfolio market value"


def test_happy_path(data):
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), answer_with(MV)])
    r = run_agent("ask", "How big is the book?", [], provider, data)

    assert r.status == "answered"
    assert "[[v" in r.answer_md
    tag = r.answer_md.split("[[")[1].split("]]")[0]
    assert r.values[tag].tool == "get_portfolio_summary"
    assert r.values[tag].method == "portfolio_aggregate"
    assert r.checks and all(c.passed for c in r.checks)
    assert [t.tool for t in r.trace] == ["get_portfolio_summary"]
    assert r.usage.llm_calls == 2
    assert r.data_date == "2026-11-16"
    assert r.fallback is None


def test_a_wrong_number_is_repaired_once(data):
    wrong = answer_with(MV, render=lambda v: f"$1.11B[[{v['id']}]]")
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), wrong, answer_with(MV)])
    r = run_agent("ask", "How big is the book?", [], provider, data)

    assert r.status == "answered"
    assert "$1.11B" not in r.answer_md
    repair_message = provider.calls[2][-1]
    assert repair_message["role"] == "tool" and "$1.11B" in repair_message["content"]
    assert r.usage.llm_calls == 3


def test_still_wrong_after_repair_is_blocked_with_no_prose(data):
    wrong = answer_with(MV, render=lambda v: f"$1.11B[[{v['id']}]]")
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), wrong, wrong])
    r = run_agent("ask", "How big is the book?", [], provider, data)

    assert r.status == "blocked"
    assert r.answer_md == "" and r.sections == []
    assert "$1.11B" not in r.model_dump_json()  # unverified text is never returned
    assert "The figure is" not in r.model_dump_json()
    assert r.fallback and any(row.label == MV for row in r.fallback)
    assert any(not c.passed for c in r.checks)


def test_invented_untagged_numbers_are_blocked(data):
    invented = tool_response("submit_answer", {"status": "answered", "answer_md": "The loss would be about $500M."})
    provider = FakeProvider([invented, invented])
    r = run_agent("ask", "Guess the loss", [], provider, data)
    assert r.status == "blocked" and r.answer_md == ""


def test_call_cap(data):
    provider = FakeProvider([tool_response("get_curve", {})] * (MAX_MODEL_CALLS + 3))
    r = run_agent("ask", "Loop forever", [], provider, data)

    assert MAX_MODEL_CALLS == 6
    assert r.status == "error"
    assert r.usage.llm_calls == MAX_MODEL_CALLS
    assert len(provider.calls) == MAX_MODEL_CALLS
    assert r.answer_md == ""


def test_provider_timeout_is_an_error_with_no_prose(data):
    provider = FakeProvider([ProviderError("model call timed out")])
    r = run_agent("ask", "Anything", [], provider, data)
    assert r.status == "error" and r.answer_md == ""


def test_cannot_answer(data):
    decline = tool_response("submit_answer", {"status": "cannot_answer", "answer_md": "Tenorwise cannot give investment advice."})
    r = run_agent("ask", "Should I buy bonds?", [], FakeProvider([decline]), data)
    assert r.status == "cannot_answer"
    assert r.answer_md == "Tenorwise cannot give investment advice."


def test_a_reply_without_a_tool_call_is_nudged(data):
    provider = FakeProvider([text_response("Let me think."), tool_response("get_portfolio_summary", {}), answer_with(MV)])
    r = run_agent("ask", "How big is the book?", [], provider, data)
    assert r.status == "answered" and r.usage.llm_calls == 3


def test_invalid_tool_arguments_go_back_to_the_model(data):
    provider = FakeProvider([
        tool_response("run_scenario", {"parallel_bp": 999}),
        tool_response("get_portfolio_summary", {}),
        answer_with(MV),
    ])
    r = run_agent("ask", "Shock it", [], provider, data)
    assert r.status == "answered"
    first_tool_result = json.loads(provider.calls[1][-1]["content"])
    assert "error" in first_tool_result


def test_history_is_text_only_and_old_tags_do_not_resolve(data):
    history = [
        {"role": "user", "content": "How big is the book?"},
        {"role": "assistant", "content": "The figure is $8.65B[[v1]]."},
    ]
    stale = tool_response("submit_answer", {"status": "answered", "answer_md": "As before, $8.65B[[v1]]."})
    provider = FakeProvider([stale, stale])
    r = run_agent("ask", "And again?", history, provider, data)

    sent = provider.calls[0]
    assert any(m["role"] == "assistant" and m["content"] == "The figure is $8.65B[[v1]]." for m in sent)
    assert r.status == "blocked"  # v1 is not in this request's ledger


def test_question_length_cap(data):
    provider = FakeProvider([])
    r = run_agent("ask", "x" * (MAX_QUESTION_CHARS + 1), [], provider, data)
    assert r.status == "error" and provider.calls == []


def test_usage_and_served_tier_are_recorded(data):
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), answer_with(MV)], model="deepseek-ai/DeepSeek-V4.1-Flash-1017")
    r = run_agent("ask", "How big?", [], provider, data)
    assert r.usage.model == "deepseek-ai/DeepSeek-V4.1-Flash-1017"
    assert r.usage.served_tier == "asap"
    assert r.usage.prompt_tokens == 2 * 100 and r.usage.completion_tokens == 2 * 20
    assert r.usage.cost_usd is not None and r.usage.cost_usd > 0


# ------------------------------------------------------------------ commentary


def commentary(sections_fn):
    def step(messages):
        return tool_response("submit_commentary", {"sections": sections_fn(last_values(messages))})
    return step


def good_sections(v):
    mv = v[MV]
    body = f"The book is worth {mv['display']}[[{mv['id']}]]."
    return [{"heading": h, "body_md": body} for h in HEADINGS]


def test_commentary_is_verified_and_marked_for_review(data):
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), commentary(good_sections)])
    r = run_agent("commentary", None, [], provider, data)

    assert r.status == "answered"
    assert [s.heading for s in r.sections] == HEADINGS
    assert r.notice == REVIEW_NOTICE == "Draft, requires human review"
    assert all(c.passed for c in r.checks)


def test_commentary_with_wrong_sections_is_sent_back(data):
    missing = commentary(lambda v: good_sections(v)[:4])
    provider = FakeProvider([tool_response("get_portfolio_summary", {}), missing, commentary(good_sections)])
    r = run_agent("commentary", None, [], provider, data)
    assert r.status == "answered"
    assert "error" in json.loads(provider.calls[2][-1]["content"])


def test_commentary_with_a_wrong_number_twice_is_blocked(data):
    def bad(v):
        return [{"heading": h, "body_md": f"The book is worth $1.11B[[{v[MV]['id']}]]."} for h in HEADINGS]

    provider = FakeProvider([tool_response("get_portfolio_summary", {}), commentary(bad), commentary(bad)])
    r = run_agent("commentary", None, [], provider, data)
    assert r.status == "blocked" and r.sections == [] and "$1.11B" not in r.model_dump_json()
