"""POST /api/agent/ask and /api/agent/commentary (PLAN.md sections 8 and 9).

Order: validate input -> daily caps (refuse if Redis is unreachable) -> model
configured? -> snapshot present? -> run the agent -> log metadata only.
Logs carry the request ID, model, tier, tokens, latency and verification
outcome; never the question text or the IP.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from tenorwise.agent.data import AgentData
from tenorwise.agent.loop import run_agent
from tenorwise.agent.provider import Provider, provider_from_env
from tenorwise.agent.schemas import AgentResponse, AskRequest, CommentaryRequest
from tenorwise.api.ratelimit import Limiter, RedisUnavailable, limiter_from_env

router = APIRouter()
logger = logging.getLogger("tenorwise.agent")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

ERRORS = {503: {"description": "AI temporarily unavailable"}, 429: {"description": "Daily limit reached"}}


def get_provider() -> Provider | None:
    return provider_from_env()


def get_limiter() -> Limiter | None:
    try:
        return limiter_from_env()
    except RedisUnavailable:
        return None


def client_ip(request: Request) -> str:
    for header in ("x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _refuse(status: int, detail: str, request_id: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail}, headers={"x-request-id": request_id})


def _handle(mode, question, history, request: Request, provider: Provider | None, limiter: Limiter | None):
    request_id = uuid.uuid4().hex
    endpoint = f"/api/agent/{'ask' if mode == 'ask' else 'commentary'}"
    if limiter is None:
        return _refuse(503, "the AI analyst is unavailable: rate limiting is not configured", request_id)
    try:
        reason = limiter.check(client_ip(request))
    except RedisUnavailable:
        return _refuse(503, "the AI analyst is unavailable: rate-limit store unreachable", request_id)
    if reason:
        return _refuse(429, reason, request_id)
    if provider is None:
        return _refuse(503, "the AI analyst is unavailable: no model is configured", request_id)
    data = AgentData.load()
    if data is None:
        return _refuse(503, "no snapshot has been built", request_id)

    result: AgentResponse = run_agent(mode, question, history, provider, data)
    result = result.model_copy(update={"request_id": request_id})
    logger.info(json.dumps({
        "event": "agent_request",
        "request_id": request_id,
        "endpoint": endpoint,
        "status": result.status,
        "model": result.usage.model,
        "served_tier": result.usage.served_tier,
        "llm_calls": result.usage.llm_calls,
        "prompt_tokens": result.usage.prompt_tokens,
        "completion_tokens": result.usage.completion_tokens,
        "cost_usd": result.usage.cost_usd,
        "latency_ms": result.usage.latency_ms,
        "checks_total": len(result.checks),
        "checks_failed": sum(not c.passed for c in result.checks),
    }, sort_keys=True))
    return JSONResponse(content=result.model_dump(mode="json"), headers={"x-request-id": request_id})


@router.post("/api/agent/ask", response_model=AgentResponse, responses=ERRORS)
def agent_ask(
    body: AskRequest, request: Request,
    provider: Provider | None = Depends(get_provider), limiter: Limiter | None = Depends(get_limiter),
):
    """Answer a plain-English question; every number is verified against the engine."""
    history = [t.model_dump() for t in body.history]
    return _handle("ask", body.question, history, request, provider, limiter)


@router.post("/api/agent/commentary", response_model=AgentResponse, responses=ERRORS)
def agent_commentary(
    request: Request, body: CommentaryRequest | None = None,
    provider: Provider | None = Depends(get_provider), limiter: Limiter | None = Depends(get_limiter),
):
    """Draft a one-page portfolio commentary (Draft, requires human review)."""
    return _handle("commentary", None, [], request, provider, limiter)
