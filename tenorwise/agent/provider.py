"""LLM provider: one interface, one OpenAI-compatible implementation, one scripted fake.

All provider specifics live here (PLAN.md section 5). Configuration comes from
LLM_BASE_URL, LLM_API_KEY and LLM_MODEL. Raw HTTP (decision log D-006):
  - POST {base}/chat/completions with max_completion_tokens; never max_tokens,
    seed, stop or penalties;
  - retries only for 429 and 503 model_capacity_unavailable / service_overloaded
    (refused before inference, so safe to repeat), honouring Retry-After with
    exponential backoff; no retry on timeouts or other errors (D-007, D-014);
  - the served tier and token usage are recorded from every response;
  - error messages never contain the API key.
"""

from __future__ import annotations

import copy
import json
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from tenorwise.paths import DATA_DIR

PRICES_FILE = DATA_DIR / "llm" / "prices.json"
RETRYABLE_503_CODES = {"model_capacity_unavailable", "service_overloaded"}


class ProviderError(Exception):
    """The model call failed. The message never contains the API key."""


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int | None  # None when the provider does not report it


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model


@dataclass(frozen=True)
class ProviderResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: Usage
    served_tier: str | None
    model: str
    latency_ms: int
    attempts: int = 1
    finish_reason: str | None = None  # "length" means the output was cut off


class Provider(Protocol):
    model: str

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: str,
        max_completion_tokens: int, timeout_s: float,
    ) -> ProviderResponse: ...


# ------------------------------------------------------------------ OpenAI-compatible


class OpenAICompatibleProvider:
    MAX_ATTEMPTS = 4

    def __init__(
        self, base_url: str, api_key: str, model: str,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0.0, 0.5),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._key = api_key
        self._transport = transport
        self._sleep = sleep
        self._jitter = jitter

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key else text

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: str,
        max_completion_tokens: int, timeout_s: float,
    ) -> ProviderResponse:
        body = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "max_completion_tokens": max_completion_tokens,
        }
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=timeout_s, transport=self._transport) as client:
            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                start = time.perf_counter()
                try:
                    r = client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
                except httpx.TimeoutException:
                    raise ProviderError("model call timed out") from None
                except httpx.HTTPError as e:
                    raise ProviderError(self._scrub(f"model call failed: {type(e).__name__}")) from None
                latency_ms = round(1000 * (time.perf_counter() - start))
                if r.status_code == 200:
                    return self._parse(r, latency_ms, attempt)
                code, message = self._error_detail(r)
                retryable = r.status_code == 429 or (r.status_code == 503 and code in RETRYABLE_503_CODES)
                if not retryable or attempt == self.MAX_ATTEMPTS:
                    detail = " ".join(x for x in (code, message) if x)
                    raise ProviderError(self._scrub(f"model call failed: HTTP {r.status_code} {detail}".strip())) from None
                delay = 2 ** (attempt - 1) + self._jitter()
                retry_after = r.headers.get("retry-after")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                self._sleep(delay)
        raise ProviderError("model call failed")  # unreachable

    @staticmethod
    def _error_detail(r: httpx.Response) -> tuple[str | None, str | None]:
        """(error code, first 200 characters of the provider's message)."""
        try:
            err = r.json().get("error") or {}
        except (ValueError, AttributeError):
            return None, None
        if not isinstance(err, dict):
            return None, str(err)[:200]
        code = err.get("code")
        message = err.get("message")
        return (str(code) if code is not None else None), (str(message)[:200] if message else None)

    def _parse(self, r: httpx.Response, latency_ms: int, attempts: int) -> ProviderResponse:
        try:
            data = r.json()
            choice = data["choices"][0]
            msg = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("model response was not in the expected format") from None
        calls = [
            ToolCall(c.get("id", ""), c["function"]["name"], c["function"].get("arguments") or "{}")
            for c in (msg.get("tool_calls") or [])
            if c.get("type", "function") == "function"
        ]
        u = data.get("usage") or {}
        details = u.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens")
        return ProviderResponse(
            content=msg.get("content"),
            tool_calls=calls,
            usage=Usage(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)),
                        int(cached) if isinstance(cached, int) else None),
            served_tier=data.get("service_tier"),
            model=data.get("model") or self.model,
            latency_ms=latency_ms,
            attempts=attempts,
            finish_reason=choice.get("finish_reason"),
        )


def provider_from_env() -> OpenAICompatibleProvider | None:
    base, key, model = (os.environ.get(v) for v in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))
    if not (base and key and model):
        return None
    return OpenAICompatibleProvider(base, key, model)


# ------------------------------------------------------------------ cost


def estimate_cost_usd(model: str, tier: str | None, usage: Usage) -> tuple[float | None, bool]:
    """(cost at list prices for the served tier, whether it is an upper bound)."""
    prices = json.loads(PRICES_FILE.read_text(encoding="utf-8"))["usd_per_million_tokens"]
    p = prices.get(model, {}).get(tier or "asap")
    if p is None:
        return None, False
    cached = usage.cached_tokens
    upper = cached is None
    cached = cached or 0
    cost = ((usage.prompt_tokens - cached) * p["input"] + cached * p["cached"] + usage.completion_tokens * p["output"]) / 1e6
    return cost, upper


# ------------------------------------------------------------------ scripted fake (tests)

Step = ProviderResponse | Exception | Callable[[list[dict[str, Any]]], ProviderResponse]


@dataclass
class FakeProvider:
    script: list[Step]
    model: str = "fake/model"
    calls: list[list[dict[str, Any]]] = field(default_factory=list)

    def complete(self, messages, tools, tool_choice, max_completion_tokens, timeout_s) -> ProviderResponse:
        self.calls.append(copy.deepcopy(messages))
        if not self.script:
            raise ProviderError("script exhausted")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        response = step(messages) if callable(step) else step
        return ProviderResponse(response.content, response.tool_calls, response.usage, response.served_tier,
                                self.model, response.latency_ms, response.attempts, response.finish_reason)


_FAKE_USAGE = Usage(100, 20, 0)
_call_counter = iter(range(1, 10**9))


def tool_response(name: str, args: dict[str, Any]) -> ProviderResponse:
    call = ToolCall(f"call_{next(_call_counter)}", name, json.dumps(args))
    return ProviderResponse(None, [call], _FAKE_USAGE, "asap", "fake/model", 5)


def text_response(content: str) -> ProviderResponse:
    return ProviderResponse(content, [], _FAKE_USAGE, "asap", "fake/model", 5)
