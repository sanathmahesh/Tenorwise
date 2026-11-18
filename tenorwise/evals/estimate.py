"""Cost estimate for an eval run, made before spending anything (ground rule 10).

Method (an estimate, not a measurement):
  1. Run the oracle, which takes the shortest tool path for each question, and
     count the characters sent on every model call (messages plus tool specs).
  2. Convert characters to prompt tokens with the ratio measured in the live
     smoke test: GLM-5.3 on 2026-11-18, SMOKE_QUESTION, 2 calls, 5,129 prompt
     tokens. The same question is replayed through the oracle to count its characters.
     Other models' tokenizers differ; the ratio is GLM's.
  3. Assume ASSUMED_COMPLETION_TOKENS_PER_CALL completion tokens per call
     (reasoning included; the smoke test measured 98 per call) and
     EXTRA_CALLS_PER_QUESTION calls beyond the oracle's minimum.
  4. Price every prompt token as uncached at the asap tier's list price
     (data/llm/prices.json). Cached tokens would make it cheaper.
"""

from __future__ import annotations

import json
import math
from typing import Any

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import run_agent
from tenorwise.agent.provider import PRICES_FILE, ProviderResponse
from tenorwise.evals.oracle import oracle_provider
from tenorwise.evals.questions import QUESTIONS, Call, Question
from tenorwise.evals.runner import SNAPSHOT

EVAL_MODELS = ("zai-org/GLM-5.3", "deepseek-ai/DeepSeek-V4.1-Flash-1017", "moonshotai/Kimi-K3.1-Pro")
SMOKE_QUESTION = "What is the portfolio's total market value and DV01?"
SMOKE_PROMPT_TOKENS = 5129  # measured, GLM-5.3, 2026-11-18 (decision log D-064)
SMOKE_COMPLETION_TOKENS = 196
SMOKE_CALLS = 2
ASSUMED_COMPLETION_TOKENS_PER_CALL = 500
EXTRA_CALLS_PER_QUESTION = 1
TIER = "asap"


class _Measure:
    def __init__(self, inner):
        self.inner, self.model, self.chars = inner, inner.model, []

    def complete(self, messages, tools, tool_choice, max_completion_tokens, timeout_s) -> ProviderResponse:
        self.chars.append(len(json.dumps(messages)) + len(json.dumps(tools)))
        return self.inner.complete(messages, tools, tool_choice, max_completion_tokens, timeout_s)


def _call_chars(q: Question, data: AgentData) -> list[int]:
    p = _Measure(oracle_provider(q))
    run_agent("ask", q.text, [], p, data)
    return p.chars


def estimate(repeats: int = 3) -> dict[str, Any]:
    data = AgentData.load(SNAPSHOT)
    smoke = Question("smoke", "lookup", SMOKE_QUESTION, lambda e: [], (Call("get_portfolio_summary"),),
                     ((0, "Portfolio market value"), (0, "Portfolio DV01")))
    smoke_chars = _call_chars(smoke, data)
    assert len(smoke_chars) == SMOKE_CALLS
    tokens_per_char = SMOKE_PROMPT_TOKENS / sum(smoke_chars)

    prompt_tokens = 0.0
    calls = 0
    for q in QUESTIONS:
        chars = _call_chars(q, data)
        prompt_tokens += tokens_per_char * (sum(chars) + EXTRA_CALLS_PER_QUESTION * chars[-1])
        calls += len(chars) + EXTRA_CALLS_PER_QUESTION
    completion_tokens = calls * ASSUMED_COMPLETION_TOKENS_PER_CALL

    prices = json.loads(PRICES_FILE.read_text(encoding="utf-8"))
    models = {}
    for m in EVAL_MODELS:
        p = prices["usd_per_million_tokens"][m][TIER]
        per_repeat = (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1e6
        total = repeats * per_repeat
        models[m] = {
            "per_question_usd": per_repeat / len(QUESTIONS),
            "total_usd": total,
            "suggested_max_cost_usd": math.ceil(20 * total) / 10,  # twice the estimate, rounded up to $0.10
        }
    return {
        "questions": len(QUESTIONS),
        "repeats": repeats,
        "tier": TIER,
        "prices_read_on": prices["read_on"],
        "calibration": {
            "question": SMOKE_QUESTION, "measured_prompt_tokens": SMOKE_PROMPT_TOKENS,
            "replayed_characters": sum(smoke_chars), "tokens_per_character": tokens_per_char,
        },
        "assumptions": {
            "completion_tokens_per_call": ASSUMED_COMPLETION_TOKENS_PER_CALL,
            "extra_calls_per_question": EXTRA_CALLS_PER_QUESTION,
            "cached_tokens": "none (all prompt tokens priced as uncached)",
        },
        "per_repeat": {"model_calls": calls, "prompt_tokens": round(prompt_tokens), "completion_tokens": completion_tokens},
        "models": models,
        "total_usd": sum(x["total_usd"] for x in models.values()),
    }
