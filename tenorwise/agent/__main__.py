"""Ask the analyst a question, or draft the commentary, from the command line.

    uv run --env-file .env python -m tenorwise.agent ask "What does the 2022 replay do to AOCI?"
    uv run --env-file .env python -m tenorwise.agent commentary
    add --fixture to use the pinned snapshot instead of data/snapshot/v1

Calls the real model configured by LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (paid).
No rate limit applies here; it is a local tool.
"""

from __future__ import annotations

import argparse
import sys

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import run_agent
from tenorwise.agent.provider import provider_from_env
from tenorwise.paths import FIXTURES_DIR


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tenorwise.agent")
    ap.add_argument("mode", choices=["ask", "commentary"])
    ap.add_argument("question", nargs="?", help="the question (ask mode)")
    ap.add_argument("--fixture", action="store_true", help="use the pinned fixture snapshot")
    args = ap.parse_args(argv)
    if args.mode == "ask" and not args.question:
        ap.error("ask needs a question")

    provider = provider_from_env()
    if provider is None:
        print("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must be set (use: uv run --env-file .env ...)", file=sys.stderr)
        return 2
    data = AgentData.load(FIXTURES_DIR / "snapshot_v1" if args.fixture else None)
    if data is None:
        print("no snapshot: run scripts/build_snapshot.py --fixture first, or pass --fixture", file=sys.stderr)
        return 2

    r = run_agent(args.mode, args.question, [], provider, data)
    print(f"Status: {r.status}    Market data date: {r.data_date}")
    if r.notice:
        print(r.notice.upper())
    print()
    if r.answer_md:
        print(r.answer_md)
    for s in r.sections:
        print(f"## {s.heading}\n{s.body_md}\n")
    if r.fallback:
        print("Blocked: unverified text withheld. Raw tool results:")
        for row in r.fallback:
            print(f"  {row.display:>18}  {row.label}  ({row.tool})")
    if r.error:
        print(f"Error: {r.error}")
    if r.values:
        print("\nCited values:")
        for vid, v in r.values.items():
            src = f"derive({', '.join(v.inputs)})" if v.inputs else f"{v.tool}({', '.join(f'{k}={a}' for k, a in v.args.items())})"
            print(f"  [{vid}] {v.display:>16}  {v.label}  <- {src}, method {v.method}")
    failed = [c for c in r.checks if not c.passed]
    print(f"\nVerification: {len(r.checks) - len(failed)}/{len(r.checks)} numbers passed")
    for c in failed:
        print(f"  FAILED {c.token} [{c.tag}]: {c.reason}")
    u = r.usage
    cost = "n/a" if u.cost_usd is None else f"${u.cost_usd:.4f}" + (" (upper bound)" if u.cost_is_upper_bound else "")
    print(f"Usage: {u.model} on {u.served_tier} tier, {u.llm_calls} calls, {u.prompt_tokens} prompt + "
          f"{u.completion_tokens} completion tokens, {cost}, {u.latency_ms} ms")
    print("Tools:", ", ".join(f"{t.tool}({t.ms} ms)" for t in r.trace) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
