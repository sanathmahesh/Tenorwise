"""Run the eval questions against one model and save every raw result (PLAN.md section 10).

One JSON object per line (JSON Lines), appended as each run finishes, so a
stopped run keeps what it has. Every reported figure is computed from these
files by report.py.

Runs are sequential (repeat 1 over all questions, then repeat 2, ...) so the
latency of one run is not inflated by our own parallel requests. Latency is
wall-clock time around the whole agent loop, measured on the machine running
the eval. The analyst sees the pinned fixture snapshot, so results are
reproducible (PLAN.md section 8).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import TAG_RE, run_agent
from tenorwise.agent.provider import PRICES_FILE, Provider, ProviderResponse
from tenorwise.evals.engine import EngineContext
from tenorwise.evals.grader import Gold, grade
from tenorwise.evals.questions import QUESTIONS, Question
from tenorwise.paths import FIXTURES_DIR, REPO_ROOT

EVALS_DIR = REPO_ROOT / "docs" / "evidence" / "evals"
RAW_DIR = EVALS_DIR / "raw"
SNAPSHOT = FIXTURES_DIR / "snapshot_v1"
VERIFIED = ("answered", "cannot_answer")


class RecordingProvider:
    """Passes calls through and keeps the last message list sent, to see whether a repair happened."""

    def __init__(self, inner: Provider):
        self.inner = inner
        self.model = inner.model
        self.last_messages: list[dict[str, Any]] = []

    def complete(self, messages, tools, tool_choice, max_completion_tokens, timeout_s) -> ProviderResponse:
        self.last_messages = list(messages)
        return self.inner.complete(messages, tools, tool_choice, max_completion_tokens, timeout_s)

    def repair_requested(self) -> bool:
        return any(m["role"] == "tool" and '"failed_checks"' in str(m.get("content")) for m in self.last_messages)


def slug(model_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", model_id)


def _gold_json(gold: list[Gold]) -> list[dict[str, Any]]:
    return [{"value": g.value, "unit": g.unit, "label": g.label, "sign_sensitive": g.sign_sensitive} for g in gold]


def run_eval(
    model_id: str,
    provider_factory: Callable[[Question], Provider],
    repeats: int = 3,
    out_dir: Path = RAW_DIR,
    max_cost_usd: float | None = None,
    questions: list[Question] | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    """Run every question `repeats` times; return the JSON Lines file written.

    max_cost_usd is a budget guard: no new run starts once the cost so far
    reaches it. Unknown costs (a model with no list price) count as zero, so
    callers must not use the guard with unpriced real models.
    """
    questions = questions if questions is not None else QUESTIONS
    data = AgentData.load(SNAPSHOT)
    engine = EngineContext.from_fixtures()
    gold = {q.id: q.gold(engine) for q in questions}
    prices_read_on = json.loads(PRICES_FILE.read_text(encoding="utf-8"))["read_on"]

    started = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug(model_id)}_{started.strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    run_id = path.stem
    spent = 0.0
    with path.open("w", encoding="utf-8") as f:
        for repeat in range(1, repeats + 1):
            for q in questions:
                if max_cost_usd is not None and spent >= max_cost_usd:
                    return path
                provider = RecordingProvider(provider_factory(q))
                t0 = time.perf_counter()
                r = run_agent("ask", q.text, [], provider, data)
                latency_ms = round(1000 * (time.perf_counter() - t0))
                tagged = dict.fromkeys(TAG_RE.findall(r.answer_md))
                values = {vid: r.values[vid].model_dump() for vid in tagged if vid in r.values}
                g = grade(q, gold[q.id], {"status": r.status, "values": values})
                repair = r.status == "blocked" or provider.repair_requested()
                row = {
                    "run_id": run_id,
                    "model": model_id,
                    "repeat": repeat,
                    "question_id": q.id,
                    "category": q.category,
                    "expected_status": q.expected_status,
                    "status": r.status,
                    "outcome": g.outcome,
                    "grade_reason": g.reason,
                    "repair_used": repair,
                    "verified": r.status in VERIFIED,
                    "answer_md": r.answer_md,
                    "values": values,
                    "gold": _gold_json(gold[q.id]),
                    "checks_failed": [c.reason for c in r.checks if not c.passed],
                    "tools": [t.tool for t in r.trace],
                    "error": r.error,
                    "latency_ms": latency_ms,
                    "llm_calls": r.usage.llm_calls,
                    "prompt_tokens": r.usage.prompt_tokens,
                    "completion_tokens": r.usage.completion_tokens,
                    "served_tier": r.usage.served_tier,
                    "cost_usd": r.usage.cost_usd,
                    "cost_is_upper_bound": r.usage.cost_is_upper_bound,
                    "prices_read_on": prices_read_on,
                    "data_date": r.data_date,
                    "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                f.write(json.dumps(row, sort_keys=True) + "\n")
                f.flush()
                spent += r.usage.cost_usd or 0.0
                if progress:
                    progress(row)
    return path
