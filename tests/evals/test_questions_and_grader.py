"""Eval questions, gold functions and the grader (PLAN.md section 10).

Gold functions call the engine directly (not the agent tools). The grader is
deterministic: no LLM judge.
"""

import math

import pytest

from tenorwise.evals.engine import EngineContext
from tenorwise.evals.grader import Gold, grade
from tenorwise.evals.questions import CATEGORIES, QUESTIONS


@pytest.fixture(scope="module")
def engine():
    return EngineContext.from_fixtures()


def test_thirty_six_questions_six_per_group():
    assert len(QUESTIONS) == 36
    ids = [q.id for q in QUESTIONS]
    assert len(set(ids)) == 36
    for cat in CATEGORIES:
        assert sum(q.category == cat for q in QUESTIONS) == 6, cat
    for q in QUESTIONS:
        assert q.expected_status == ("cannot_answer" if q.category == "decline" else "answered"), q.id


def test_gold_functions_are_stable_against_the_engine(engine):
    again = EngineContext.from_fixtures()
    for q in QUESTIONS:
        first, second = q.gold(engine), q.gold(again)
        assert first == second, q.id
        if q.expected_status == "answered":
            assert first and all(math.isfinite(g.value) for g in first), q.id
        else:
            assert first == [], q.id


def test_gold_values_agree_with_what_the_tools_can_see(engine):
    """Spot checks: engine gold equals the snapshot the tools read (within float noise)."""
    from tenorwise.agent.data import AgentData
    from tenorwise.paths import FIXTURES_DIR

    snap = AgentData.load(FIXTURES_DIR / "snapshot_v1")
    by_id = {q.id: q for q in QUESTIONS}
    assert by_id["A2"].gold(engine)[0].value == pytest.approx(snap.portfolio["summary"]["market_value"], rel=1e-9)
    replay = next(s for s in snap.scenarios["scenarios"] if s["id"] == "replay_2022")
    assert by_id["B3"].gold(engine)[0].value == pytest.approx(replay["total"]["htm_unrecognized"], rel=1e-9)


# ------------------------------------------------------------------ grader case table


def response(status, values=(), repair_used=False):
    return {
        "status": status,
        "repair_used": repair_used,
        "values": {f"v{i + 1}": {"value": v, "unit": u} for i, (v, u) in enumerate(values)},
    }


ANSWERED = type("Q", (), {"expected_status": "answered"})()
DECLINE = type("Q", (), {"expected_status": "cannot_answer"})()
G = [Gold(-370_600_000.0, "usd", "change")]

GRADER_CASES = [
    ("exact value", ANSWERED, G, response("answered", [(-370_600_000.0, "usd")]), "pass"),
    ("within 0.5%", ANSWERED, G, response("answered", [(-371_000_000.0, "usd")]), "pass"),
    ("outside 0.5%", ANSWERED, G, response("answered", [(-373_000_000.0, "usd")]), "fail"),
    ("value missing", ANSWERED, G, response("answered", [(1.0, "usd")]), "fail"),
    ("wrong unit", ANSWERED, G, response("answered", [(-370_600_000.0, "usd_per_bp")]), "fail"),
    ("wrong sign", ANSWERED, G, response("answered", [(370_600_000.0, "usd")]), "fail"),
    ("sign-insensitive gold", ANSWERED, [Gold(-339.8e6, "usd", "diff", sign_sensitive=False)],
     response("answered", [(339.8e6, "usd")]), "pass"),
    ("all of several golds", ANSWERED, G + [Gold(4.93, "pct", "rate")],
     response("answered", [(-370_600_000.0, "usd"), (4.93, "pct")]), "pass"),
    ("one of several golds missing", ANSWERED, G + [Gold(4.93, "pct", "rate")],
     response("answered", [(-370_600_000.0, "usd")]), "fail"),
    ("blocked", ANSWERED, G, response("blocked"), "blocked"),
    ("error", ANSWERED, G, response("error"), "fail"),
    ("declined when it should answer", ANSWERED, G, response("cannot_answer"), "fail"),
    ("declined correctly", DECLINE, [], response("cannot_answer"), "pass"),
    ("answered when it should decline", DECLINE, [], response("answered", [(1.0, "usd")]), "fail"),
    ("zero gold needs zero", ANSWERED, [Gold(0.0, "usd", "zero")], response("answered", [(0.0, "usd")]), "pass"),
]


@pytest.mark.parametrize(("name", "q", "gold", "resp", "expected"), GRADER_CASES, ids=[c[0] for c in GRADER_CASES])
def test_grader_case_table(name, q, gold, resp, expected):
    assert grade(q, gold, resp).outcome == expected
