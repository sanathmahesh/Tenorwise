"""Full dry run of the eval pipeline with fake providers (no network, no cost).

1. An "oracle" fake that makes each question's reference tool calls and cites
   the gold labels must score 100%: every question is answerable through the
   tools, and runner + grader + report agree end to end.
2. A fake that declines everything must score exactly the 6 decline questions.
"""

import json

import pytest

from tenorwise.evals.oracle import oracle_provider
from tenorwise.evals.questions import QUESTIONS
from tenorwise.evals.report import summarize
from tenorwise.evals.runner import run_eval
from tenorwise.agent.provider import FakeProvider, tool_response


def test_oracle_scores_100_percent_and_report_is_consistent(tmp_path):
    path = run_eval("oracle/fake", lambda q: oracle_provider(q), repeats=2, out_dir=tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]

    assert len(rows) == 36 * 2
    failed = [(r["question_id"], r["outcome"], r.get("grade_reason")) for r in rows if r["outcome"] != "pass"]
    assert failed == []

    summary = summarize([path])
    m = summary["models"][0]
    assert m["id"] == "oracle/fake"
    assert m["accuracy"] == 1.0 and m["accuracy_min"] == 1.0 and m["accuracy_max"] == 1.0
    assert m["block_rate"] == 0.0 and m["verified_but_wrong_rate"] == 0.0
    assert m["runs"] == 2
    assert {q["id"] for q in summary["questions"]} == {q.id for q in QUESTIONS}
    assert all(q["results"]["oracle/fake"] == "pass" for q in summary["questions"])


def test_declining_everything_scores_only_the_decline_group(tmp_path):
    def decliner(q):
        return FakeProvider([tool_response("submit_answer", {"status": "cannot_answer", "answer_md": "I cannot answer that."})])

    path = run_eval("decliner/fake", decliner, repeats=1, out_dir=tmp_path)
    summary = summarize([path])
    m = summary["models"][0]
    assert m["accuracy"] == pytest.approx(6 / 36)
    assert m["verified_but_wrong_rate"] == pytest.approx(30 / 36)  # passed verification (no numbers) but wrong
    assert m["block_rate"] == 0.0


def test_budget_guard_stops_scheduling(tmp_path):
    """No new run starts once the cost so far reaches the budget."""
    priced = "deepseek-ai/DeepSeek-V4.1-Flash-1017"  # a priced model name, so fake usage has a cost
    nothing = run_eval(priced, lambda q: oracle_provider(q, model=priced), repeats=1, out_dir=tmp_path / "a",
                       max_cost_usd=0.0)
    assert nothing.read_text() == ""

    some = run_eval(priced, lambda q: oracle_provider(q, model=priced), repeats=1, out_dir=tmp_path / "b",
                    max_cost_usd=1e-5)
    rows = [json.loads(line) for line in some.read_text().splitlines()]
    assert 0 < len(rows) < 36
    assert sum(r["cost_usd"] for r in rows[:-1]) < 1e-5 <= sum(r["cost_usd"] for r in rows)
