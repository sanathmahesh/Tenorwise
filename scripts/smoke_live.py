"""Smoke test against a deployed Tenorwise (PLAN.md Phase 12).

    uv run python scripts/smoke_live.py https://tenorwise.vercel.app [--max-ai 12] [--pace 15]

Checks: the health endpoint; the site serves the app; the static data date matches the
API's and is recent; one AI question is answered with every number verified; and a 429
arrives once the per-IP daily limit is passed. PAID: each allowed AI request is a real
model call (the cap's worth of requests, mostly cheap declined questions). Prints a
cost total from the responses' reported usage. Prints no secrets and no headers.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import httpx

QUESTION = "What is the portfolio's total market value?"
PROBE = "Where will the 10-year Treasury yield be next year?"  # declined: one cheap model call
MAX_DATA_AGE_DAYS = 7  # the build's own staleness rule (ASSUMPTIONS A-05)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class SmokeResult:
    checks: list[Check] = field(default_factory=list)
    ai_requests: int = 0
    cost_usd: float = 0.0
    cost_unknown: bool = False


def limit_source(r: httpx.Response) -> str:
    """Who sent a 429: the app's per-IP daily cap ("app"), its global cap ("global"), or something in front
    of the app, such as the Vercel firewall rule ("firewall")."""
    try:
        detail = str(r.json().get("detail", ""))
    except ValueError:
        return "firewall"
    return "app" if "per-IP" in detail else "global" if "global" in detail else "firewall"


def _ask(api: httpx.Client, question: str, result: SmokeResult) -> httpx.Response:
    r = api.post("/api/agent/ask", json={"question": question, "history": []})
    result.ai_requests += 1
    if r.status_code == 200:
        cost = r.json().get("usage", {}).get("cost_usd")
        if cost is None:
            result.cost_unknown = True
        else:
            result.cost_usd += cost
    return r


def run_smoke(api: httpx.Client, site: httpx.Client, today: date, max_ai: int = 12, pace_s: float = 0.0,
              sleep: Callable[[float], None] = time.sleep) -> SmokeResult:
    res = SmokeResult()
    add = lambda name, ok, detail: res.checks.append(Check(name, bool(ok), detail))  # noqa: E731

    h = api.get("/api/health")
    health = h.json() if h.status_code == 200 else {}
    add("health", h.status_code == 200 and health.get("status") == "ok" and health.get("data_date") and health.get("model_id"),
        f"HTTP {h.status_code}, status {health.get('status')}, data date {health.get('data_date')}, "
        f"build {health.get('build_time')}, git {health.get('git_sha')}, model {health.get('model_id')}")

    home = site.get("/")
    add("site serves the app", home.status_code == 200 and "Tenorwise" in home.text, f"HTTP {home.status_code}")

    m = site.get("/data/v1/meta.json")
    meta_date = m.json().get("data_date") if m.status_code == 200 else None
    add("data date matches", meta_date is not None and meta_date == health.get("data_date"),
        f"meta.json {meta_date}, health {health.get('data_date')}")
    age = (today - date.fromisoformat(meta_date)).days if meta_date else None
    add("data date is recent", age is not None and 0 <= age <= MAX_DATA_AGE_DAYS, f"{age} days old on {today.isoformat()}")

    r = _ask(api, QUESTION, res)
    body = r.json() if r.status_code == 200 else {}
    checks = body.get("checks", [])
    add("AI question answered and verified",
        r.status_code == 200 and body.get("status") == "answered" and checks and all(c["passed"] for c in checks) and body.get("values"),
        f"HTTP {r.status_code}, status {body.get('status')}, {sum(c['passed'] for c in checks)}/{len(checks)} numbers verified, "
        f"model {body.get('usage', {}).get('model')}")

    last = r
    while last.status_code != 429 and res.ai_requests < max_ai:
        if pace_s:
            sleep(pace_s)  # stay under a burst rule in front of the app, so the 429 tested is the app's own
        last = _ask(api, PROBE, res)
    if last.status_code != 429:
        add("429 once the per-IP limit is passed", False, f"no 429 within {res.ai_requests} AI requests")
    else:
        source = limit_source(last)
        add("429 once the per-IP limit is passed", source == "app",
            f"after {res.ai_requests} AI requests" if source == "app" else
            f"the 429 came from the {source} limit, not the per-IP daily cap; rerun with --pace")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="smoke_live.py")
    ap.add_argument("url", help="e.g. https://tenorwise.vercel.app")
    ap.add_argument("--max-ai", type=int, default=12, help="most AI requests to send while looking for the 429")
    ap.add_argument("--pace", type=float, default=0.0, help="seconds between AI requests, to stay under a firewall burst rule")
    args = ap.parse_args(argv)
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as client:
        res = run_smoke(client, client, today=date.today(), max_ai=args.max_ai, pace_s=args.pace)
    for c in res.checks:
        print(f"{'PASS' if c.passed else 'FAIL'}  {c.name}: {c.detail}")
    cost = "unknown" if res.cost_unknown and res.cost_usd == 0 else f"${res.cost_usd:.4f}" + (" (some unknown)" if res.cost_unknown else "")
    print(f"AI requests: {res.ai_requests}; model cost at list prices: {cost}")
    return 0 if all(c.passed for c in res.checks) else 1


if __name__ == "__main__":
    sys.exit(main())
