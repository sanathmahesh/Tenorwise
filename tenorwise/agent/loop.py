"""The analyst's loop (PLAN.md section 9).

At most MAX_MODEL_CALLS model calls per request. The model must answer through a
tool call (submit_answer or submit_commentary). Its text is verified against
the request's ledger. If verification fails, the failed checks go back as the
tool result and the model gets one repair attempt. If that also fails, the
response is "blocked": no prose at all, plus a deterministic table of the raw
tool results. Unverified text is never returned.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal

from pydantic import ValidationError

from tenorwise.agent.data import AgentData
from tenorwise.agent.ledger import Ledger
from tenorwise.agent.provider import Provider, ProviderError, Usage, estimate_cost_usd
from tenorwise.agent.schemas import (
    AgentResponse,
    CheckOut,
    FallbackRow,
    SectionOut,
    TraceOut,
    UsageOut,
    ValueOut,
)
from tenorwise.agent.tools import (
    COMMENTARY_HEADINGS,
    SUBMIT_TOOL,
    SubmitAnswerArgs,
    SubmitCommentaryArgs,
    run_tool,
    tool_specs,
)
from tenorwise.agent.verifier import TOLERANCE_TEXT, Check, all_passed, verify

MAX_MODEL_CALLS = 6
MAX_QUESTION_CHARS = 1000
MAX_HISTORY_MESSAGES = 10
MAX_COMPLETION_TOKENS = 4096
CALL_TIMEOUT_S = 60.0
REVIEW_NOTICE = "Draft, requires human review"
TAG_RE = re.compile(r"\[\[(v\d+)\]\]")

Mode = Literal["ask", "commentary"]

RULES = """Rules you must follow:
1. Never calculate. Every number you state must come from a tool result. If you need a figure no tool returns (a sum, difference, ratio or percent change), call derive with the value IDs.
2. Write each number exactly as its display string, immediately followed by its tag, for example: falls by -$412.3M[[v12]]. Copy the display string; do not round, reformat or convert it.
3. You may state without a tag only: tenors, shock sizes, hedge ratios, the 12-month horizon, and dates that appear in your tool calls or tool results.
4. Value IDs exist only for this request. Earlier turns are context only; to state a number again, fetch it again.
5. Agency mortgage bonds are stylized (illustrative prepayment model) and the IG corporates sleeve is a proxy; say so when relevant.
6. Plain English, no investment advice."""

SYSTEM = {
    "ask": """You are the analyst for Tenorwise, an interest-rate risk and hedging tool for a model bank bond portfolio (about $10B, mix based on BNY's 10-Q). Market data date: {date}.
Answer the user's question using the tools, then call submit_answer. Keep the answer under 150 words.
If the tools cannot answer (a forecast, a security not in the portfolio, an estimate without the engine, or investment advice), call submit_answer with status "cannot_answer" and say briefly why, without numbers.
""" + RULES,
    "commentary": """You are the analyst for Tenorwise, an interest-rate risk and hedging tool for a model bank bond portfolio (about $10B, mix based on BNY's 10-Q). Market data date: {date}.
Draft a one-page portfolio commentary of about 400 words for a bank's investment committee. Gather the figures with the tools first (portfolio summary, a few scenarios, hedge comparison), then call submit_commentary with exactly five sections, in this order: Positioning, Rate sensitivity, Scenario results, Hedging trade-off, Caveats.
""" + RULES,
}
COMMENTARY_REQUEST = "Draft the portfolio commentary."
NUDGE = "Respond with a tool call. Finish with {submit}."


def _seed_context(ledger: Ledger, data: AgentData) -> None:
    """Fixed descriptors the model may state untagged."""
    for m in (1, 3, 6, 12):
        ledger.add_context(m, "months", "tenor or horizon")
    for y in (1, 2, 3, 5, 7, 10, 20, 30):
        ledger.add_context(y, "years", "tenor")
    for bp in (1, 25, 50, 75, 100, 200, 300):
        ledger.add_context(bp, "bp", "shock size")
        ledger.add_context(-bp, "bp", "shock size")
    for pct in (50, 100):
        ledger.add_context(pct, "pct", "hedge ratio")
    for iso in {data.data_date, "2021-12-31", "2022-12-30", "2026-09-30", "2026-10-30",
                data.mbs["mortgage_rate"]["date"]}:
        ledger.add_context_date(iso)
    ledger.add_context(2022, None, "replay year")


def _cited(texts: list[str], ledger: Ledger) -> dict[str, ValueOut]:
    out: dict[str, ValueOut] = {}
    for text in texts:
        for vid in TAG_RE.findall(text):
            v = ledger.values.get(vid)
            if v is None:
                continue
            out[vid] = ValueOut(value=v.value, unit=v.unit, display=v.display, label=v.label, tool=v.tool,
                                args=v.args, method=v.method, inputs=v.inputs)
            for parent in v.inputs:  # include derive inputs so the provenance chain resolves
                out.update(_cited([f"[[{parent}]]"], ledger))
    return out


class _Run:
    def __init__(self, mode: Mode, provider: Provider, data: AgentData | None):
        self.mode, self.provider, self.data = mode, provider, data
        self.ledger = Ledger()
        self.trace: list[TraceOut] = []
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens: int | None = 0
        self.tiers: list[str] = []
        self.started = time.perf_counter()

    def record(self, usage: Usage, tier: str | None) -> None:
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        if usage.cached_tokens is None or self.cached_tokens is None:
            self.cached_tokens = None
        else:
            self.cached_tokens += usage.cached_tokens
        if tier:
            self.tiers.append(tier)

    def finish(
        self, status: str, answer_md: str = "", sections: list[SectionOut] | None = None,
        checks: list[Check] | None = None, error: str | None = None,
    ) -> AgentResponse:
        tier = None
        if self.tiers:
            tier = self.tiers[-1] if len(set(self.tiers)) == 1 else "mixed"
        cost, upper = estimate_cost_usd(self.provider.model, tier,
                                        Usage(self.prompt_tokens, self.completion_tokens, self.cached_tokens))
        verified = status in ("answered", "cannot_answer")
        texts = [answer_md] + [s.body_md for s in (sections or [])]
        if not verified:
            # A failed token is unverified text: withhold it, keep the tag and the reason.
            checks = [c if c.passed else Check("(withheld)", c.tag, False, c.reason) for c in (checks or [])]
        return AgentResponse(
            status=status,
            answer_md=answer_md if verified else "",
            sections=(sections or []) if verified else [],
            values=_cited(texts, self.ledger) if verified else {},
            checks=[CheckOut(token=c.token, tag=c.tag, passed=c.passed, reason=c.reason) for c in (checks or [])],
            trace=self.trace,
            usage=UsageOut(model=self.provider.model, served_tier=tier, llm_calls=self.calls,
                           prompt_tokens=self.prompt_tokens, completion_tokens=self.completion_tokens,
                           cost_usd=cost, latency_ms=round(1000 * (time.perf_counter() - self.started)),
                           cost_is_upper_bound=upper),
            fallback=[FallbackRow(tool=v.tool, label=v.label, display=v.display) for v in self.ledger.values.values()]
            if status == "blocked" else None,
            data_date=self.data.data_date if self.data else None,
            notice=REVIEW_NOTICE if self.mode == "commentary" else None,
            error=error,
            verification_rule=TOLERANCE_TEXT,
        )


def run_agent(
    mode: Mode, question: str | None, history: list[dict[str, str]], provider: Provider,
    data: AgentData | None, call_timeout_s: float = CALL_TIMEOUT_S,
) -> AgentResponse:
    run = _Run(mode, provider, data)
    if data is None:
        return run.finish("error", error="no snapshot has been built")
    if mode == "ask" and (not question or len(question) > MAX_QUESTION_CHARS):
        return run.finish("error", error=f"the question must be 1 to {MAX_QUESTION_CHARS} characters")
    _seed_context(run.ledger, data)

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM[mode].format(date=data.data_date)}]
    for turn in history[-MAX_HISTORY_MESSAGES:]:
        messages.append({"role": turn["role"], "content": str(turn["content"])})
    messages.append({"role": "user", "content": question if mode == "ask" else COMMENTARY_REQUEST})
    tools = tool_specs(mode)
    submit_name = SUBMIT_TOOL[mode]
    repaired = False

    while run.calls < MAX_MODEL_CALLS:
        try:
            resp = provider.complete(messages, tools, "required", MAX_COMPLETION_TOKENS, call_timeout_s)
        except ProviderError as e:
            return run.finish("error", error=str(e))
        run.record(resp.usage, resp.served_tier)

        if not resp.tool_calls:
            messages.append({"role": "assistant", "content": resp.content or ""})
            messages.append({"role": "user", "content": NUDGE.format(submit=submit_name)})
            continue
        messages.append({
            "role": "assistant",
            "content": resp.content,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                           for c in resp.tool_calls],
        })

        submit = None
        for call in resp.tool_calls:
            if call.name == submit_name and submit is None:
                submit = call
                continue
            try:
                args = json.loads(call.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError
            except ValueError:
                result: dict[str, Any] = {"error": "arguments are not a JSON object"}
                args = {}
            else:
                t0 = time.perf_counter()
                result = run_tool(call.name, args, run.ledger, data)
                run.trace.append(TraceOut(tool=call.name, args=args, ms=round(1000 * (time.perf_counter() - t0))))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

        if submit is None:
            continue
        outcome = _submit(mode, submit.arguments, run.ledger)
        if isinstance(outcome, str):  # invalid arguments: send back, not a repair attempt
            messages.append({"role": "tool", "tool_call_id": submit.id, "content": json.dumps({"error": outcome})})
            continue
        status, answer_md, sections, checks = outcome
        if all_passed(checks):
            return run.finish(status, answer_md, sections, checks)
        if repaired:
            return run.finish("blocked", checks=checks)
        repaired = True
        failed = [{"token": c.token, "tag": c.tag, "reason": c.reason} for c in checks if not c.passed]
        messages.append({"role": "tool", "tool_call_id": submit.id, "content": json.dumps({
            "error": "verification failed; fix every listed number and submit again (one attempt left)",
            "failed_checks": failed,
        })})

    return run.finish("error", error=f"no verified answer within {MAX_MODEL_CALLS} model calls")


def _submit(mode: Mode, raw: str, ledger: Ledger):
    """Validate and verify a submission. Returns an error string, or (status, answer, sections, checks)."""
    try:
        args = json.loads(raw or "{}")
        parsed = (SubmitAnswerArgs if mode == "ask" else SubmitCommentaryArgs).model_validate(args)
    except (ValueError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return f"invalid arguments: {e.errors(include_url=False, include_input=False)}"
        return "arguments are not valid JSON"
    if mode == "ask":
        return parsed.status, parsed.answer_md, None, verify(parsed.answer_md, ledger)
    sections = [SectionOut(heading=s.heading, body_md=s.body_md) for s in parsed.sections]
    assert tuple(s.heading for s in sections) == COMMENTARY_HEADINGS
    text = "\n\n".join(s.body_md for s in sections)
    return "answered", "", sections, verify(text, ledger)
