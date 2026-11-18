"""The oracle: a scripted fake model that follows each question's reference plan.

Used only in the dry run (no network, no cost). It makes the plan's tool calls
in order, then submits an answer that cites the plan's values by copying their
display strings and tags. If the oracle scores 100%, every question is
answerable through the tools, and the tools, the runner, the grader and the
report agree with the engine end to end. It says nothing about how hard a
question is for a real model.
"""

from __future__ import annotations

import json
from typing import Any

from tenorwise.agent.provider import FakeProvider, tool_response
from tenorwise.evals.questions import Call, Derive, Question, Ref

DECLINE_TEXT = "Tenorwise cannot answer this: it is outside what the engine produces, or it asks for advice or a guess."


class PlanError(AssertionError):
    """The reference plan does not work against the tools (a bug in the question set)."""


def _tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


def _lookup(q: Question, results: list[dict[str, Any]], ref: Ref) -> dict[str, Any]:
    step, label = ref
    if step >= len(results) or "values" not in results[step]:
        raise PlanError(f"{q.id}: step {step} returned no values: {results[step] if step < len(results) else 'missing'}")
    found = [v for v in results[step]["values"] if v["label"] == label]
    if len(found) != 1:
        raise PlanError(f"{q.id}: step {step} has {len(found)} values labelled {label!r}")
    return found[0]


def oracle_provider(q: Question, model: str = "oracle/fake") -> FakeProvider:
    def tool_step(i: int):
        def step(messages):
            item = q.plan[i]
            if isinstance(item, Call):
                return tool_response(item.tool, item.args)
            assert isinstance(item, Derive)
            results = _tool_results(messages)
            ids = [_lookup(q, results, r)["id"] for r in item.operands]
            return tool_response("derive", {"operation": item.operation, "operands": ids, "label": item.label})
        return step

    def submit(messages):
        if q.expected_status == "cannot_answer":
            return tool_response("submit_answer", {"status": "cannot_answer", "answer_md": DECLINE_TEXT})
        results = _tool_results(messages)
        cited = [_lookup(q, results, r) for r in q.cite]
        text = "The answer is " + " and ".join(f"{v['display']}[[{v['id']}]]" for v in cited) + "."
        return tool_response("submit_answer", {"status": "answered", "answer_md": text})

    return FakeProvider([tool_step(i) for i in range(len(q.plan))] + [submit], model=model)
