"""Request and response contract for /api/agent/ask and /api/agent/commentary (PLAN.md section 8).

Fields marked "added" go beyond the plan's list; none of the plan's names changed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValueOut(Contract):
    value: float
    unit: str
    display: str
    label: str
    tool: str
    args: dict[str, Any]
    method: str
    inputs: list[str]


class CheckOut(Contract):
    token: str
    tag: str | None
    passed: bool
    reason: str


class TraceOut(Contract):
    tool: str
    args: dict[str, Any]
    ms: int


class UsageOut(Contract):
    model: str
    served_tier: str | None
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    latency_ms: int
    cost_is_upper_bound: bool = Field(description="added: cached tokens were not reported")


class SectionOut(Contract):
    heading: str
    body_md: str


class FallbackRow(Contract):
    tool: str
    label: str
    display: str


class AgentResponse(Contract):
    status: Literal["answered", "cannot_answer", "blocked", "error"]
    answer_md: str
    sections: list[SectionOut]
    values: dict[str, ValueOut]
    checks: list[CheckOut]
    trace: list[TraceOut]
    usage: UsageOut
    fallback: list[FallbackRow] | None
    data_date: str | None
    notice: str | None = Field(None, description="added: 'Draft, requires human review' on commentary")
    error: str | None = Field(None, description="added: why status is error")
    request_id: str | None = Field(None, description="added")
    verification_rule: str = Field(description="added: the stated tolerance, for display")


class HistoryTurn(Contract):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AskRequest(Contract):
    question: str = Field(min_length=1, max_length=1000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=10)


class CommentaryRequest(Contract):
    pass
