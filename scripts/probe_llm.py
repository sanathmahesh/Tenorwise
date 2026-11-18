"""Phase 0 provider probe: does each candidate model do what Tenorwise needs?

    uv run --env-file .env python scripts/probe_llm.py [MODEL_ID ...]

For each model (default: the three in PLAN.md section 4) it tests, against
POST {LLM_BASE_URL}/chat/completions:
  1. plain       a plain completion;
  2. tool_trip   a function-tool round trip (call -> tool result -> answer),
                 with no service_tier set, so the provider default applies;
  3. required    tool_choice "required" with service_tier "asap" set explicitly,
                 which shows whether function tools run on the asap tier;
  4. json_schema a response_format json_schema reply that must parse and match;
and on every response it records the usage fields and the served tier.
For GLM-5.3 it also confirms the documented HTTP 400 for reasoning_effort "none".

Raw findings go to docs/provider-probe.md (readable) and
docs/provider-probe-raw.json (full response bodies). The API key is read from
the environment, never printed, and the output files are checked for it
before they are written.

Cost: every call is capped at MAX_COMPLETION_TOKENS output tokens.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

DEFAULT_MODELS = [
    "zai-org/GLM-5.3",
    "deepseek-ai/DeepSeek-V4.1-Flash-1017",
    "moonshotai/Kimi-K3.1-Pro",
]

# Default (ASAP) list prices in USD per 1M tokens, re-read from
# https://docs.sailresearch.com/pricing.md on 2026-11-17. Used only to estimate
# what this probe cost; they match PLAN.md section 4.
ASAP_PRICES = {
    "zai-org/GLM-5.3": {"input": 0.98, "cached": 0.18, "output": 3.08},
    "deepseek-ai/DeepSeek-V4.1-Flash-1017": {"input": 0.09, "cached": 0.006, "output": 0.30},
    "moonshotai/Kimi-K3.1-Pro": {"input": 1.50, "cached": 0.20, "output": 10.00},
}
PRICES_SOURCE = "https://docs.sailresearch.com/pricing.md (read 2026-11-17)"

MAX_COMPLETION_TOKENS = 1024
REQUEST_TIMEOUT_S = 120.0
MAX_ATTEMPTS = 4

SYNTHETIC_RATE = 1.2345  # probe-only test value, not market data

GET_RATE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_rate",
        "description": (
            "Return the synthetic test rate, in percent, for a tenor in years. "
            "Probe only; not market data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tenor_years": {"type": "number", "description": "Tenor in years, e.g. 10"}
            },
            "required": ["tenor_years"],
            "additionalProperties": False,
        },
    },
}

JSON_SCHEMA_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "capital_city",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "capital": {"type": "string"},
            },
            "required": ["country", "capital"],
            "additionalProperties": False,
        },
    },
}

RETRYABLE_503_CODES = {"model_capacity_unavailable", "service_overloaded"}


# --------------------------------------------------------------------------- HTTP


class Client:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        # Auth header lives only inside the httpx client; it is never recorded.
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=REQUEST_TIMEOUT_S,
        )

    def list_models(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            r = self._http.get(f"{self.base_url}/models")
            body = _safe_json(r)
            return {
                "http_status": r.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "body": body,
            }
        except httpx.HTTPError as exc:
            return {"http_status": None, "error": f"{type(exc).__name__}: {exc}"}

    def chat(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /chat/completions with retries only for refused-before-inference errors."""
        attempts: list[dict[str, Any]] = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.perf_counter()
            try:
                r = self._http.post(f"{self.base_url}/chat/completions", json=body)
            except httpx.HTTPError as exc:
                # Timeouts and connection errors are "uncertain" per retries.md:
                # the request may have started, so the probe does not retry them.
                attempts.append({"attempt": attempt, "error": f"{type(exc).__name__}: {exc}"})
                return {"attempts": attempts, "http_status": None, "body": None}
            latency_ms = round((time.perf_counter() - start) * 1000)
            resp_body = _safe_json(r)
            record = {
                "attempt": attempt,
                "http_status": r.status_code,
                "latency_ms": latency_ms,
                "retry_after": r.headers.get("retry-after"),
                "request_id": r.headers.get("x-request-id"),
            }
            attempts.append(record)
            if not _is_retryable(r.status_code, resp_body) or attempt == MAX_ATTEMPTS:
                return {
                    "attempts": attempts,
                    "http_status": r.status_code,
                    "latency_ms": latency_ms,
                    "request_id": record["request_id"],
                    "body": resp_body,
                }
            delay = 2 ** (attempt - 1) + random.uniform(0, 0.5)
            if record["retry_after"]:
                try:
                    delay = max(delay, float(record["retry_after"]))
                except ValueError:
                    pass
            time.sleep(delay)
        raise AssertionError("unreachable")


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return {"non_json_body": r.text[:2000]}


def _is_retryable(status: int, body: Any) -> bool:
    if status == 429:
        return True
    if status == 503 and isinstance(body, dict):
        code = (body.get("error") or {}).get("code")
        return code in RETRYABLE_503_CODES
    return False


# ------------------------------------------------------------------------- checks


def _message(result: dict[str, Any]) -> dict[str, Any] | None:
    body = result.get("body")
    if result.get("http_status") != 200 or not isinstance(body, dict):
        return None
    choices = body.get("choices") or []
    return choices[0].get("message") if choices else None


def _finish_reason(result: dict[str, Any]) -> str | None:
    body = result.get("body")
    if isinstance(body, dict) and body.get("choices"):
        return body["choices"][0].get("finish_reason")
    return None


def _usage_ok(result: dict[str, Any]) -> bool:
    body = result.get("body")
    if not isinstance(body, dict):
        return False
    usage = body.get("usage") or {}
    return all(isinstance(usage.get(k), int) for k in ("prompt_tokens", "completion_tokens", "total_tokens"))


def _base(model: str, messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        **extra,
    }


def test_plain(client: Client, model: str) -> dict[str, Any]:
    body = _base(model, [{"role": "user", "content": "Reply with exactly one word: pong"}])
    result = client.chat(body)
    msg = _message(result)
    content = (msg or {}).get("content") or ""
    passed = "pong" in content.lower()
    return _finish("plain", body, [result], passed,
                   "content contains 'pong'" if passed else f"content={content[:200]!r}")


def test_tool_round_trip(client: Client, model: str) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You answer by calling the provided tools."},
        {"role": "user", "content": "Look up the rate for a 10-year tenor with get_rate, then tell me the rate."},
    ]
    body1 = _base(model, messages, tools=[GET_RATE_TOOL], tool_choice="auto")
    r1 = client.chat(body1)
    msg1 = _message(r1)
    calls = (msg1 or {}).get("tool_calls") or []
    if not calls:
        return _finish("tool_trip", body1, [r1], False, "no tool call on the first turn")
    call = calls[0]
    fn = call.get("function") or {}
    try:
        args = json.loads(fn.get("arguments") or "")
    except ValueError:
        return _finish("tool_trip", body1, [r1], False, f"arguments are not JSON: {fn.get('arguments')!r}")
    if fn.get("name") != "get_rate" or args.get("tenor_years") != 10:
        return _finish("tool_trip", body1, [r1], False, f"unexpected call {fn.get('name')}({args})")

    # Send the assistant turn back with only schema-allowed fields (role,
    # content, tool_calls); the request schema forbids extra message fields.
    assistant_turn = {"role": "assistant", "content": msg1.get("content"), "tool_calls": calls}
    tool_turn = {
        "role": "tool",
        "tool_call_id": call.get("id"),
        "content": json.dumps({"tenor_years": 10, "rate_pct": SYNTHETIC_RATE, "note": "synthetic probe value"}),
    }
    body2 = _base(model, messages + [assistant_turn, tool_turn], tools=[GET_RATE_TOOL], tool_choice="auto")
    r2 = client.chat(body2)
    msg2 = _message(r2)
    content = (msg2 or {}).get("content") or ""
    passed = str(SYNTHETIC_RATE) in content
    detail = (
        f"called get_rate({args}); final answer quotes {SYNTHETIC_RATE}"
        if passed
        else f"final answer missing {SYNTHETIC_RATE}: {content[:200]!r}"
    )
    return _finish("tool_trip", body2, [r1, r2], passed, detail, first_body=body1)


def test_required_on_asap(client: Client, model: str) -> dict[str, Any]:
    body = _base(
        model,
        [{"role": "user", "content": "Hello there."}],
        tools=[GET_RATE_TOOL],
        tool_choice="required",
        service_tier="asap",
    )
    result = client.chat(body)
    msg = _message(result)
    calls = (msg or {}).get("tool_calls") or []
    served = (result.get("body") or {}).get("service_tier") if isinstance(result.get("body"), dict) else None
    passed = bool(calls) and served == "asap"
    if passed:
        detail = f"tool call returned on served tier {served!r}"
    elif result.get("http_status") != 200:
        detail = f"HTTP {result.get('http_status')}"
    else:
        detail = f"tool_calls={len(calls)}, served tier {served!r}"
    return _finish("required", body, [result], passed, detail)


def test_json_schema(client: Client, model: str) -> dict[str, Any]:
    body = _base(
        model,
        [{"role": "user", "content": "Give the country France and its capital city as JSON."}],
        response_format=JSON_SCHEMA_FORMAT,
    )
    result = client.chat(body)
    msg = _message(result)
    content = (msg or {}).get("content") or ""
    try:
        parsed = json.loads(content)
    except ValueError:
        return _finish("json_schema", body, [result], False, f"content is not JSON: {content[:200]!r}")
    keys_ok = isinstance(parsed, dict) and set(parsed) == {"country", "capital"}
    types_ok = keys_ok and all(isinstance(v, str) for v in parsed.values())
    passed = bool(types_ok)
    return _finish("json_schema", body, [result], passed,
                   f"parsed {parsed}" if passed else f"schema mismatch: {parsed}")


def test_glm_reasoning_none(client: Client, model: str) -> dict[str, Any]:
    body = _base(model, [{"role": "user", "content": "Reply with exactly one word: pong"}], reasoning_effort="none")
    result = client.chat(body)
    passed = result.get("http_status") == 400
    return _finish("glm_none_400", body, [result], passed,
                   f"HTTP {result.get('http_status')} (docs say 400)")


def _finish(
    name: str,
    body: dict[str, Any],
    results: list[dict[str, Any]],
    passed: bool,
    detail: str,
    first_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "test": name,
        "passed": passed,
        "detail": detail,
        "request_body": first_body or body,
        "responses": results,
    }


# ------------------------------------------------------------------------ report


def call_cost(model: str, usage: dict[str, Any]) -> tuple[float, bool]:
    """Cost at ASAP list prices. Returns (usd, cached_tokens_reported)."""
    prices = ASAP_PRICES.get(model)
    if not prices:
        return 0.0, False
    prompt = usage.get("prompt_tokens") or 0
    completion = usage.get("completion_tokens") or 0
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens")
    cached_reported = isinstance(cached, int)
    cached = cached if cached_reported else 0
    usd = ((prompt - cached) * prices["input"] + cached * prices["cached"] + completion * prices["output"]) / 1e6
    return usd, cached_reported


def render_markdown(run: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Provider probe (Phase 0)")
    add("")
    add(f"- Run at: {run['run_at']} (UTC), from the developer's machine")
    add(f"- Endpoint: `POST {run['base_url']}/chat/completions` (Bearer auth; key not recorded)")
    add(f"- Every call capped at `max_completion_tokens={MAX_COMPLETION_TOKENS}`; no `max_tokens`, `seed`, `stop` or penalties sent")
    add(f"- Retries: only 429 and 503 `{'`/`'.join(sorted(RETRYABLE_503_CODES))}`, honouring `Retry-After`, at most {MAX_ATTEMPTS} attempts")
    add("- Generated by `scripts/probe_llm.py`. Full response bodies: `docs/provider-probe-raw.json`")
    add("")
    add("## Model list (`GET /v1/models`)")
    add("")
    listed = run["models_listed"]
    add(f"HTTP {listed.get('http_status')}. Candidate models present:")
    add("")
    ids = {m.get("id") for m in ((listed.get("body") or {}).get("data") or []) if isinstance(m, dict)}
    for model in run["models"]:
        add(f"- `{model}`: {'listed' if model in ids else 'NOT LISTED'}")
    sample = ((listed.get("body") or {}).get("data") or [])[:1]
    add("")
    add(f"Shape of one entry (fields returned): `{json.dumps(sample[0]) if sample else 'n/a'}`")
    add("")
    add("## Summary")
    add("")
    add("| Model | plain | tool round trip (default tier) | tool_choice required on `asap` | json_schema | usage fields | served tiers seen |")
    add("|---|---|---|---|---|---|---|")
    for model, mres in run["results"].items():
        by = {t["test"]: t for t in mres["tests"]}

        def cell(name: str) -> str:
            t = by.get(name)
            return "n/a" if t is None else ("PASS" if t["passed"] else "**FAIL**")

        add(
            f"| `{model}` | {cell('plain')} | {cell('tool_trip')} | {cell('required')} | "
            f"{cell('json_schema')} | {'PASS' if mres['usage_ok'] else '**FAIL**'} | "
            f"{', '.join(sorted(mres['served_tiers'])) or 'none reported'} |"
        )
    add("")
    add(f"Probe cost at list prices ({PRICES_SOURCE}): **${run['total_cost_usd']:.4f}** in total"
        + ("" if run["all_cached_reported"] else " (upper bound: not every response reported cached tokens, so all input is priced as uncached)")
        + ". Computed from the usage each response reported; not read from a Sail invoice.")
    add("")
    for model, mres in run["results"].items():
        add(f"## `{model}`")
        add("")
        for t in mres["tests"]:
            add(f"### {t['test']}: {'PASS' if t['passed'] else 'FAIL'}")
            add("")
            add(f"{t['detail']}")
            add("")
            req = {k: v for k, v in t["request_body"].items() if k not in {"messages", "tools", "response_format"}}
            add(f"Request parameters (besides messages/tools/format): `{json.dumps(req)}`")
            add("")
            for i, res in enumerate(t["responses"], start=1):
                body = res.get("body") if isinstance(res.get("body"), dict) else {}
                msg = (body.get("choices") or [{}])[0].get("message") if body.get("choices") else None
                add(f"Call {i}: HTTP {res.get('http_status')}, {res.get('latency_ms')} ms, attempts {len(res.get('attempts', []))}, "
                    f"served tier `{body.get('service_tier')}`, finish_reason `{_finish_reason(res)}`, response id `{body.get('id')}`")
                add("")
                if body.get("usage") is not None:
                    add(f"- usage: `{json.dumps(body.get('usage'), sort_keys=True)}`")
                if msg:
                    content = msg.get("content")
                    if content:
                        shown = content if len(content) <= 400 else content[:400] + f"... [{len(content)} chars total]"
                        add(f"- content: `{shown!s}`".replace("\n", " "))
                    if msg.get("tool_calls"):
                        add(f"- tool_calls: `{json.dumps(msg['tool_calls'])}`")
                    rc = msg.get("reasoning_content")
                    if rc:
                        add(f"- reasoning_content: {len(rc)} chars (omitted here; in the raw JSON)")
                    extra = sorted(set(msg) - {"role", "content", "tool_calls", "reasoning_content"})
                    if extra:
                        add(f"- other message fields: `{extra}`")
                if "error" in body or res.get("http_status") != 200:
                    add(f"- error body: `{json.dumps(body)[:600]}`")
                add("")
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    if not base_url or not api_key:
        print("LLM_BASE_URL and LLM_API_KEY must be set (use: uv run --env-file .env ...)", file=sys.stderr)
        return 2
    models = argv or DEFAULT_MODELS
    client = Client(base_url, api_key)

    run: dict[str, Any] = {
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": base_url.rstrip("/"),
        "models": models,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "models_listed": client.list_models(),
        "results": {},
    }

    total_cost = 0.0
    all_cached_reported = True
    for model in models:
        print(f"probing {model} ...", flush=True)
        tests = [
            test_plain(client, model),
            test_tool_round_trip(client, model),
            test_required_on_asap(client, model),
            test_json_schema(client, model),
        ]
        if model == "zai-org/GLM-5.3":
            tests.append(test_glm_reasoning_none(client, model))
        ok_responses = [r for t in tests for r in t["responses"] if r.get("http_status") == 200]
        served = {r["body"].get("service_tier") for r in ok_responses if isinstance(r.get("body"), dict)}
        served.discard(None)
        for r in ok_responses:
            usd, cached_reported = call_cost(model, r["body"].get("usage") or {})
            total_cost += usd
            all_cached_reported &= cached_reported
        run["results"][model] = {
            "tests": tests,
            "usage_ok": bool(ok_responses) and all(_usage_ok(r) for r in ok_responses),
            "served_tiers": sorted(served),
        }
        for t in tests:
            print(f"  {t['test']:<12} {'PASS' if t['passed'] else 'FAIL'}  {t['detail']}", flush=True)

    run["total_cost_usd"] = total_cost
    run["all_cached_reported"] = all_cached_reported

    markdown = render_markdown(run)
    raw = json.dumps(run, indent=2, sort_keys=True, default=str) + "\n"
    for text in (markdown, raw):
        if api_key in text:
            print("refusing to write: output contains the API key", file=sys.stderr)
            return 3
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "provider-probe.md").write_text(markdown, encoding="utf-8")
    (DOCS_DIR / "provider-probe-raw.json").write_text(raw, encoding="utf-8")
    print(f"probe cost at list prices: ${total_cost:.4f}"
          + ("" if all_cached_reported else " (upper bound: cached tokens not reported)"))
    print("wrote docs/provider-probe.md and docs/provider-probe-raw.json")

    blocking = [
        f"{model}: {t['test']}"
        for model, mres in run["results"].items()
        for t in mres["tests"]
        if t["test"] in {"tool_trip", "required"} and not t["passed"]
    ]
    if blocking:
        print("BLOCKING (tool calling or tools-on-asap failed): " + "; ".join(blocking), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
