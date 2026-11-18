"""OpenAI-compatible provider: request shape, retries, usage, cost (PLAN.md sections 4 and 9).

No network: httpx.MockTransport. Retries only for 429 and 503
model_capacity_unavailable / service_overloaded (D-014).
"""

import json

import httpx
import pytest

from tenorwise.agent.provider import (
    OpenAICompatibleProvider,
    ProviderError,
    estimate_cost_usd,
)

KEY = "sk-synthetic-test-key-0123456789"
MESSAGES = [{"role": "user", "content": "hi"}]
TOOLS = [{"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object", "properties": {}}}}]


def ok_body(tier="asap", cached=0):
    return {
        "id": "resp_1",
        "model": "m/model",
        "service_tier": tier,
        "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
        }}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                  "prompt_tokens_details": {"cached_tokens": cached}},
    }


def provider(handler, sleeps=None):
    sleeps = sleeps if sleeps is not None else []
    return OpenAICompatibleProvider(
        base_url="https://llm.example/v1", api_key=KEY, model="m/model",
        transport=httpx.MockTransport(handler), sleep=sleeps.append, jitter=lambda: 0.0,
    )


def test_request_shape_and_parsed_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_body())

    r = provider(handler).complete(MESSAGES, TOOLS, tool_choice="required", max_completion_tokens=512, timeout_s=30)

    body = seen["body"]
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert body["max_completion_tokens"] == 512
    assert body["tool_choice"] == "required" and body["tools"] == TOOLS and body["model"] == "m/model"
    for banned in ("max_tokens", "seed", "stop", "frequency_penalty", "presence_penalty", "logit_bias", "n", "functions"):
        assert banned not in body
    assert r.tool_calls[0].name == "f" and r.tool_calls[0].arguments == "{}"
    assert r.served_tier == "asap"
    assert (r.usage.prompt_tokens, r.usage.completion_tokens, r.usage.cached_tokens) == (100, 20, 0)
    assert r.attempts == 1


@pytest.mark.parametrize(
    ("status", "body", "headers"),
    [
        (503, {"error": {"code": "model_capacity_unavailable", "message": "busy"}}, {"retry-after": "2"}),
        (503, {"error": {"code": "service_overloaded", "message": "busy"}}, {}),
        (429, {"error": {"code": "rate_limited", "message": "slow down"}}, {"retry-after": "3"}),
    ],
    ids=["503-capacity", "503-overloaded", "429"],
)
def test_retries_refused_before_inference_errors_with_backoff(status, body, headers):
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(status, json=body, headers=headers)
        return httpx.Response(200, json=ok_body())

    r = provider(handler, sleeps).complete(MESSAGES, TOOLS, "required", 512, 30)

    assert r.attempts == 2 and len(calls) == 2
    assert sleeps and sleeps[0] >= float(headers.get("retry-after", 0))


@pytest.mark.parametrize(
    ("status", "body"),
    [(500, {"error": {"code": "internal"}}), (503, {"error": {"code": "something_else"}}), (400, {"error": {"code": "bad"}})],
    ids=["500", "503-other", "400"],
)
def test_other_errors_are_not_retried(status, body):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, json=body)

    with pytest.raises(ProviderError):
        provider(handler).complete(MESSAGES, TOOLS, "required", 512, 30)
    assert len(calls) == 1


def test_gives_up_after_max_attempts():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, json={"error": {"code": "model_capacity_unavailable"}})

    with pytest.raises(ProviderError):
        provider(handler).complete(MESSAGES, TOOLS, "required", 512, 30)
    assert len(calls) == OpenAICompatibleProvider.MAX_ATTEMPTS


def test_timeout_is_an_error_and_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        provider(handler).complete(MESSAGES, TOOLS, "required", 512, 30)
    assert len(calls) == 1


def test_errors_never_contain_the_key():
    def handler(request):
        return httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": f"bad key {KEY}"}})

    with pytest.raises(ProviderError) as e:
        provider(handler).complete(MESSAGES, TOOLS, "required", 512, 30)
    assert KEY not in str(e.value) and e.value.__cause__ is None


def test_cost_uses_list_prices_for_the_served_tier():
    from tenorwise.agent.provider import Usage

    cost, upper = estimate_cost_usd("deepseek-ai/DeepSeek-V4.1-Flash-1017", "asap", Usage(1_000_000, 1_000_000, 0))
    assert cost == pytest.approx(0.09 + 0.30) and upper is False
    cost, _ = estimate_cost_usd("deepseek-ai/DeepSeek-V4.1-Flash-1017", "asap", Usage(1_000_000, 0, 500_000))
    assert cost == pytest.approx(0.5 * 0.09 + 0.5 * 0.006)
    cost, upper = estimate_cost_usd("zai-org/GLM-5.3", "asap", Usage(1_000_000, 0, None))
    assert cost == pytest.approx(0.98) and upper is True  # cached tokens not reported: upper bound
    assert estimate_cost_usd("unknown/model", "asap", Usage(1, 1, 0)) == (None, False)
