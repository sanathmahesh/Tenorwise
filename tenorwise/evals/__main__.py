"""Eval commands (PLAN.md section 10, Phase 9).

    uv run python -m tenorwise.evals dry-run      # the full pipeline with the oracle fake; free, no network
    uv run python -m tenorwise.evals estimate     # cost estimate for 3 repeats of the 3 models; free
    uv run --env-file .env python -m tenorwise.evals run --model zai-org/GLM-5.3 --max-cost 2.00     # PAID
    uv run python -m tenorwise.evals report       # summary.json and report.md from every raw file

`run` calls the real model (LLM_BASE_URL, LLM_API_KEY; the model comes from
--model) and appends each result to docs/evidence/evals/raw/. It refuses to
start unless data/llm/prices.json was re-read from Sail's pricing page today,
and it starts no new question once the cost so far reaches --max-cost.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from tenorwise.agent.provider import PRICES_FILE, OpenAICompatibleProvider
from tenorwise.evals.estimate import EVAL_MODELS, estimate
from tenorwise.evals.oracle import oracle_provider
from tenorwise.evals.questions import QUESTIONS
from tenorwise.evals.report import REPORT_FILE, SUMMARY_FILE, render_markdown, summarize, write_report
from tenorwise.evals.runner import RAW_DIR, run_eval
from tenorwise.paths import REPO_ROOT


def refuse_reason(model: str, prices: Mapping[str, Any], today: date, env: Mapping[str, str]) -> str | None:
    if not (env.get("LLM_BASE_URL") and env.get("LLM_API_KEY")):
        return "LLM_BASE_URL and LLM_API_KEY must be set (use: uv run --env-file .env ...)"
    if model not in prices["usd_per_million_tokens"]:
        return f"{model} has no list price in data/llm/prices.json, so the budget guard cannot work"
    if prices["read_on"] != today.isoformat():
        return (f"prices were read on {prices['read_on']}: re-read Sail's pricing page today and update "
                "data/llm/prices.json (PLAN.md section 10)")
    return None


def _models_table(summary: dict[str, Any]) -> str:
    md = render_markdown(summary)
    return md[md.index("## By model"):md.index("## Accuracy by group")].strip()


def cmd_run(args: argparse.Namespace) -> int:
    prices = json.loads(PRICES_FILE.read_text(encoding="utf-8"))
    reason = refuse_reason(args.model, prices, date.today(), os.environ)
    if reason:
        print(f"Refusing to run: {reason}", file=sys.stderr)
        return 2
    provider = OpenAICompatibleProvider(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], args.model)
    total = len(QUESTIONS) * args.repeats
    print(f"Model {args.model}: {len(QUESTIONS)} questions x {args.repeats} repeats = {total} runs; "
          f"budget ${args.max_cost:.2f}; prices read {prices['read_on']}")
    state = {"n": 0, "spent": 0.0}

    def progress(row: dict[str, Any]) -> None:
        state["n"] += 1
        state["spent"] += row["cost_usd"] or 0.0
        print(f"[{state['n']:>3}/{total}] repeat {row['repeat']} {row['question_id']}: {row['outcome']:<7} "
              f"({row['status']}{', repaired' if row['repair_used'] else ''}) {row['latency_ms'] / 1000:5.1f} s  "
              f"${row['cost_usd'] or 0:.4f}  spent ${state['spent']:.3f}", flush=True)

    path = run_eval(args.model, lambda q: provider, repeats=args.repeats, max_cost_usd=args.max_cost, progress=progress)
    if state["n"] < total:
        print(f"Stopped after {state['n']} of {total} runs: the budget of ${args.max_cost:.2f} was reached.")
    print(f"Raw results: {path.relative_to(REPO_ROOT)}\nNext: uv run python -m tenorwise.evals report")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        summary = write_report()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(_models_table(summary))
    print(f"\nWrote {SUMMARY_FILE.relative_to(REPO_ROOT)} and {REPORT_FILE.relative_to(REPO_ROOT)} "
          f"from {len(summary['source_files'])} raw file(s) in {RAW_DIR.relative_to(REPO_ROOT)}.")
    print("Rebuild the snapshot (scripts/build_snapshot.py) to publish them in evidence.json.")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as d:
        path = run_eval("oracle/fake", oracle_provider, repeats=1, out_dir=Path(d))
        summary = summarize([path])
    failed = [q["id"] for q in summary["questions"] if q["results"].get("oracle/fake") != "pass"]
    print("Dry run: the oracle fake (no network, no cost) follows each question's reference plan.\n")
    print(_models_table(summary))
    print(f"\n{len(QUESTIONS) - len(failed)}/{len(QUESTIONS)} questions passed" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


def cmd_estimate(args: argparse.Namespace) -> int:
    e = estimate(repeats=args.repeats)
    c, a, r = e["calibration"], e["assumptions"], e["per_repeat"]
    print(f"Estimate (not a measurement) for {e['questions']} questions x {e['repeats']} repeats per model, "
          f"{e['tier']} tier, prices read {e['prices_read_on']}:")
    print(f"  per repeat: {r['model_calls']} model calls, ~{r['prompt_tokens']:,} prompt + {r['completion_tokens']:,} completion tokens")
    print(f"  calibration: {c['measured_prompt_tokens']:,} prompt tokens measured for the smoke question "
          f"= {c['tokens_per_character']:.3f} tokens per character (GLM-5.3 tokenizer)")
    print(f"  assumed: {a['completion_tokens_per_call']} completion tokens per call, "
          f"{a['extra_calls_per_question']} extra call per question, no cached-token discount")
    for m, x in e["models"].items():
        print(f"  {m:<40} ${x['per_question_usd']:.4f} per question  ${x['total_usd']:.2f} total  "
              f"(suggested --max-cost {x['suggested_max_cost_usd']:.2f})")
    print(f"  all three models: ${e['total_usd']:.2f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.evals")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the evals against one real model (paid)")
    run.add_argument("--model", required=True, choices=EVAL_MODELS)
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--max-cost", type=float, required=True, help="budget in US dollars; no new question starts beyond it")
    run.set_defaults(func=cmd_run)
    sub.add_parser("report", help="summarize every raw results file").set_defaults(func=cmd_report)
    sub.add_parser("dry-run", help="the full pipeline with the oracle fake (free)").set_defaults(func=cmd_dry_run)
    est = sub.add_parser("estimate", help="estimate the cost of a run (free)")
    est.add_argument("--repeats", type=int, default=3)
    est.set_defaults(func=cmd_estimate)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
