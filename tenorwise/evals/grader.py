"""Deterministic grader (PLAN.md section 10). No LLM judge.

An answer is correct if its status matches the expected status and every gold
value appears among the values the answer cites, with the same unit and within
the verifier's tolerance (0.5%). A blocked answer is graded "blocked", which
counts as not correct.

"Cited" means tagged in the answer text itself. The agent's response also
carries the inputs of any derived value (for provenance); those do not count,
so the runner passes only the directly tagged values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from tenorwise.agent.verifier import RELATIVE_TOLERANCE

ABS_TOLERANCE = 1e-9  # only matters when the gold value is exactly zero

Outcome = Literal["pass", "fail", "blocked"]


@dataclass(frozen=True)
class Gold:
    value: float
    unit: str
    label: str
    # False for differences whose order the question leaves open ("how much more ...")
    sign_sensitive: bool = True


@dataclass(frozen=True)
class Grade:
    outcome: Outcome
    reason: str


def _close(cited: float, gold: float) -> bool:
    return abs(cited - gold) <= RELATIVE_TOLERANCE * abs(gold) + ABS_TOLERANCE


def matches(g: Gold, cited: dict[str, Any]) -> bool:
    if cited.get("unit") != g.unit:
        return False
    c = float(cited["value"])
    return _close(c, g.value) or (not g.sign_sensitive and _close(-c, g.value))


def grade(question: Any, gold: list[Gold], response: dict[str, Any]) -> Grade:
    """question needs .expected_status; response needs status and values {id: {value, unit}}."""
    status = response["status"]
    if status == "blocked":
        return Grade("blocked", "verification blocked the answer after the repair attempt")
    if status != question.expected_status:
        return Grade("fail", f"status {status}, expected {question.expected_status}")
    cited = list((response.get("values") or {}).values())
    missing = [g for g in gold if not any(matches(g, c) for c in cited)]
    if missing:
        return Grade("fail", "not cited: " + "; ".join(f"{g.label} ({g.unit})" for g in missing))
    return Grade("pass", "status matches and every gold value is cited" if gold else "status matches")
