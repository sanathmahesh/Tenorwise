"""FastAPI application. Exposed to Vercel by api/index.py.

Request-path rule: nothing here may import pandas or QuantLib
(tests/api/test_import_isolation.py enforces this).
"""

import importlib.util
import os
import platform
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from tenorwise.snapshot.store import read_json

app = FastAPI(
    title="Tenorwise API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


class HealthResponse(BaseModel):
    status: Literal["ok", "no_snapshot"]
    data_date: str | None
    build_time: str | None
    git_sha: str | None
    model_id: str | None


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


class DeployCheckResponse(BaseModel):
    note: str
    build_check: dict[str, Any] | None
    runtime: dict[str, Any]
    importable: dict[str, bool]


@app.get("/api/deploy-check", response_model=DeployCheckResponse)
def deploy_check() -> DeployCheckResponse:
    """Phase 0 only (removed once the real snapshot exists in Phase 7).

    Proves three things about the deployed function: it can read a file the
    build step wrote, numpy and scipy are installed and work, and QuantLib and
    pandas are not installed.
    """
    import numpy as np
    import scipy
    from scipy.optimize import brentq

    return DeployCheckResponse(
        note="Phase 0 deploy check (temporary endpoint)",
        build_check=read_json("build_check.json"),
        runtime={
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "brentq_sqrt2": brentq(lambda x: x * x - 2.0, 0.0, 2.0, xtol=1e-15),
        },
        # find_spec checks installation without importing the package.
        importable={
            name: importlib.util.find_spec(name) is not None for name in ("pandas", "QuantLib")
        },
    )
