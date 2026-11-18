"""Summarize raw eval results (PLAN.md section 10). Every reported figure comes from here.

Per model, from its raw JSON Lines files:
  - accuracy: share of runs graded "pass"; the mean over repeats, with the
    lowest and highest repeat (Sail offers no seed, so repeats differ);
  - block rate before repair: share of runs whose first submission failed
    verification (a repair was requested);
  - block rate (after repair): share of runs that ended "blocked";
  - verified-but-wrong rate: of the runs that passed verification (status
    answered or cannot_answer), the share graded wrong. This is the failure the
    verifier cannot catch: every number was copied correctly, but the answer
    was the wrong one;
  - latency p50 and p95 in ms, wall-clock on the eval machine;
  - cost per question: mean of each run's cost at list prices for the served
    tier, flagged as an upper bound if any run's usage lacked cached tokens.

Per question and model, the evidence result is the outcome of the majority of
repeats; with no majority it is "fail".

pandas is allowed here (ground rule 6) but not needed; numpy computes percentiles.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from tenorwise.evals.questions import BY_ID, CATEGORIES, CATEGORY_NAMES
from tenorwise.evals.runner import EVALS_DIR, RAW_DIR

SUMMARY_FILE = EVALS_DIR / "summary.json"
REPORT_FILE = EVALS_DIR / "report.md"
LATENCY_NOTE = "Wall-clock per question on the eval machine (one network location, sequential runs), not the deployed app."


def load_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _share(n: int, d: int) -> float:
    return n / d if d else 0.0


def _majority(outcomes: list[str]) -> str:
    top, count = Counter(outcomes).most_common(1)[0]
    return top if count > len(outcomes) / 2 else "fail"


def _model_summary(model: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    repeats: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        repeats[(r["run_id"], r["repeat"])].append(r)
    per_repeat = [_share(sum(r["outcome"] == "pass" for r in rs), len(rs)) for rs in repeats.values()]
    complete = all(len({r["question_id"] for r in rs}) == len(BY_ID) for rs in repeats.values())
    verified = [r for r in rows if r["verified"]]
    costs = [r["cost_usd"] for r in rows]
    latencies = [r["latency_ms"] for r in rows]
    by_category = {
        c: _share(sum(r["outcome"] == "pass" for r in rows if r["category"] == c),
                  sum(r["category"] == c for r in rows))
        for c in CATEGORIES
    }
    return {
        "id": model,
        "runs": len(repeats),
        "questions_run": len(rows),
        "complete": complete,
        "accuracy": float(np.mean(per_repeat)),
        "accuracy_min": min(per_repeat),
        "accuracy_max": max(per_repeat),
        "accuracy_by_category": by_category,
        "block_rate_before_repair": _share(sum(r["repair_used"] for r in rows), len(rows)),
        "block_rate": _share(sum(r["status"] == "blocked" for r in rows), len(rows)),
        "error_rate": _share(sum(r["status"] == "error" for r in rows), len(rows)),
        "verified_but_wrong_rate": _share(sum(r["outcome"] == "fail" for r in verified), len(verified)),
        "verified_runs": len(verified),
        "latency_p50_ms": float(np.percentile(latencies, 50)),
        "latency_p95_ms": float(np.percentile(latencies, 95)),
        "cost_per_question_usd": None if any(c is None for c in costs) else float(np.mean(costs)),
        "cost_total_usd": None if any(c is None for c in costs) else float(np.sum(costs)),
        "cost_is_upper_bound": any(r["cost_is_upper_bound"] for r in rows),
        "prices_read_on": sorted({r["prices_read_on"] for r in rows}),
        "served_tiers": sorted({str(r["served_tier"]) for r in rows}),
        "mean_llm_calls": float(np.mean([r["llm_calls"] for r in rows])),
    }


def summarize(paths: Iterable[Path]) -> dict[str, Any]:
    paths = list(paths)
    rows = load_rows(paths)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    models = [_model_summary(m, rs) for m, rs in sorted(by_model.items())]

    outcomes: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in rows:
        outcomes[(r["question_id"], r["model"])].append(r["outcome"])
    questions = [
        {
            "id": q.id,
            "category": q.category,
            "text": q.text,
            "results": {m: _majority(outcomes[(q.id, m)]) for m in by_model if outcomes[(q.id, m)]},
            "counts": {m: dict(Counter(outcomes[(q.id, m)])) for m in by_model if outcomes[(q.id, m)]},
        }
        for q in BY_ID.values()
    ]
    return {
        "source_files": sorted(Path(p).name for p in paths),
        "latency_note": LATENCY_NOTE,
        "models": models,
        "questions": questions,
    }


# ------------------------------------------------------------------ markdown


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _usd(x: float | None, upper: bool) -> str:
    return "n/a" if x is None else f"${x:.4f}" + (" (upper bound)" if upper else "")


def render_markdown(summary: dict[str, Any]) -> str:
    out = [
        "# Eval results",
        "",
        "Generated by `python -m tenorwise.evals report` from the raw files in `docs/evidence/evals/raw/`. "
        "Do not edit by hand.",
        "",
        "Grading is deterministic: an answer is correct if its status matches and every gold value is cited "
        "within the verifier's tolerance (0.5%). Gold values come from the engine run directly, not from the agent's tools.",
        "",
        "## By model",
        "",
        "| Model | Repeats | Accuracy, mean (range) | Blocked before repair | Blocked after repair | "
        "Verified but wrong | Errors | Latency p50 / p95 | Cost per question | Mean model calls |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in summary["models"]:
        rng = f"{_pct(m['accuracy'])} ({_pct(m['accuracy_min'])} to {_pct(m['accuracy_max'])})"
        out.append(
            f"| `{m['id']}` | {m['runs']}{'' if m['complete'] else ' (incomplete)'} | {rng} | "
            f"{_pct(m['block_rate_before_repair'])} | {_pct(m['block_rate'])} | {_pct(m['verified_but_wrong_rate'])} | "
            f"{_pct(m['error_rate'])} | {m['latency_p50_ms'] / 1000:.1f} s / {m['latency_p95_ms'] / 1000:.1f} s | "
            f"{_usd(m['cost_per_question_usd'], m['cost_is_upper_bound'])} | {m['mean_llm_calls']:.1f} |"
        )
    out += [
        "",
        f"Latency: {summary['latency_note']}",
        "",
        "Cost: token usage at Sail's list prices for the served tier, prices read on "
        + ", ".join(sorted({d for m in summary["models"] for d in m["prices_read_on"]}) or ["n/a"])
        + ". Not read from an invoice. \"Upper bound\" means the provider did not report cached tokens, "
        "so all prompt tokens were priced as uncached.",
        "",
        "Verified but wrong: of the answers that passed verification, the share graded wrong.",
        "",
        "## Accuracy by group",
        "",
        "| Group | " + " | ".join(f"`{m['id']}`" for m in summary["models"]) + " |",
        "|---|" + "---|" * len(summary["models"]),
    ]
    for c in CATEGORIES:
        out.append(f"| {CATEGORY_NAMES[c]} | " + " | ".join(_pct(m["accuracy_by_category"][c]) for m in summary["models"]) + " |")
    out += [
        "",
        "## By question",
        "",
        "Result is the majority outcome over the repeats (no majority counts as fail); counts in brackets.",
        "",
        "| ID | Question | " + " | ".join(f"`{m['id']}`" for m in summary["models"]) + " |",
        "|---|---|" + "---|" * len(summary["models"]),
    ]
    for q in summary["questions"]:
        cells = []
        for m in summary["models"]:
            res = q["results"].get(m["id"], "not run")
            counts = ", ".join(f"{k} {v}" for k, v in sorted(q["counts"].get(m["id"], {}).items()))
            cells.append(f"{res} ({counts})" if counts else res)
        out.append(f"| {q['id']} | {q['text']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def write_report(raw_dir: Path = RAW_DIR, summary_file: Path = SUMMARY_FILE, report_file: Path = REPORT_FILE) -> dict[str, Any]:
    paths = sorted(raw_dir.glob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"no raw results in {raw_dir}")
    summary = summarize(paths)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    report_file.write_text(render_markdown(summary), encoding="utf-8")
    return summary
