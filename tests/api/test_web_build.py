"""Frontend: type-checks, builds, carries no secrets; API types are up to date.

Runs `npm run build` in web/ (tsc -b && vite build). Needs `npm ci --prefix web`.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tenorwise.api.openapi import build_openapi

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
DIST = WEB / "dist"
SECRET_VARS = ("FRED_API_KEY", "LLM_API_KEY", "UPSTASH_REDIS_REST_TOKEN", "UPSTASH_REDIS_REST_URL", "IP_HASH_SALT")
KEY_LIKE = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}"),
    re.compile(r"api_key=[A-Za-z0-9]{8,}"),
    re.compile(r"(?<![A-Za-z0-9])[a-z0-9]{32}(?![A-Za-z0-9])"),  # FRED keys are 32 lowercase alphanumerics
]


@pytest.fixture(scope="module")
def built():
    if not (WEB / "node_modules").exists():
        pytest.fail("web/node_modules missing: run `npm ci --prefix web` first")
    result = subprocess.run(["npm", "run", "build", "--prefix", str(WEB)], capture_output=True, text=True, timeout=300)
    return result


def secret_values() -> list[str]:
    values = [os.environ[v] for v in SECRET_VARS if len(os.environ.get(v, "")) >= 8]
    for name in (".env", ".env.local"):
        path = REPO / name
        if path.exists():
            for line in path.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"').strip("'")
                    if key.strip() not in ("LLM_BASE_URL", "LLM_MODEL") and len(value) >= 8:
                        values.append(value)
    return values


def test_frontend_type_checks_and_builds(built):
    assert built.returncode == 0, built.stdout[-3000:] + built.stderr[-3000:]
    assert (DIST / "index.html").exists()


def test_built_bundle_contains_no_key_or_key_like_variable(built):
    assert built.returncode == 0
    secrets = secret_values()
    for path in DIST.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for var in SECRET_VARS + ("VITE_",):
            assert var not in text, (str(path.relative_to(REPO)), var)
        for value in secrets:
            assert value not in text, (str(path.relative_to(REPO)), "a configured secret value")  # never print it
        for pattern in KEY_LIKE:
            match = pattern.search(text)
            assert match is None, (str(path.relative_to(REPO)), pattern.pattern)


def test_committed_openapi_schema_matches_the_app():
    committed = json.loads((REPO / "docs" / "api" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build_openapi())), "run scripts/export_openapi.py and npm run gen:types"


def test_generated_typescript_types_exist_and_cover_the_contract():
    types = (WEB / "src" / "api" / "schema.d.ts").read_text(encoding="utf-8")
    for name in ("Meta", "Curve", "Portfolio", "Mbs", "Scenarios", "Hedges", "Methods", "Evidence",
                 "ScenarioRequest", "ScenarioResponse", "HealthResponse"):
        assert re.search(rf"\b{name}:", types), name
