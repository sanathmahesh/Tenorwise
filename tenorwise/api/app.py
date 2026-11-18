"""FastAPI application. Exposed to Vercel by api/index.py.

Request-path rule: nothing here may import pandas or QuantLib
(tests/api/test_import_isolation.py enforces this).
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tenorwise.api.agent_routes import router as agent_router
from tenorwise.api.scenario import run_custom
from tenorwise.snapshot.models import HealthResponse, ScenarioRequest, ScenarioResponse
from tenorwise.snapshot.store import read_json

app = FastAPI(
    title="Tenorwise API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    separate_input_output_schemas=False,
)
app.include_router(agent_router)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    meta = read_json("meta.json")
    model_id = os.environ.get("LLM_MODEL") or None
    if meta is None:
        return HealthResponse(
            status="no_snapshot", data_date=None, build_time=None, git_sha=None, model_id=model_id
        )
    return HealthResponse(
        status="ok",
        data_date=meta.get("data_date"),
        build_time=meta.get("build_time"),
        git_sha=meta.get("git_sha"),
        model_id=model_id,
    )


@app.post(
    "/api/scenario",
    response_model=ScenarioResponse,
    responses={503: {"description": "No snapshot has been built"}},
)
def scenario(req: ScenarioRequest) -> JSONResponse:
    """Custom parallel shift (-300 to +300 bp) or custom key-rate shocks (-300 to +300 bp each)."""
    body = run_custom(req)
    if body is None:
        return JSONResponse(status_code=503, content={"detail": "no snapshot has been built"})
    return JSONResponse(content=body)
