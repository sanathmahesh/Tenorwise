"""GET /api/health: status, data date, build time, git SHA, model ID.

The values in these tests are synthetic fixtures, not market data.
"""

import json

import pytest
from fastapi.testclient import TestClient

from tenorwise.api.app import app

SYNTHETIC_META = {
    "data_date": "2000-01-03",
    "build_time": "2000-01-04T12:00:00Z",
    "git_sha": "abc1234",
    "fred_series": [],
    "llm_model": None,
    "assumptions": [],
}


@pytest.fixture
def client():
    return TestClient(app)


def test_health_reports_snapshot_metadata(client, tmp_path, monkeypatch):
    (tmp_path / "meta.json").write_text(json.dumps(SYNTHETIC_META))
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_MODEL", "test-org/test-model")

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "data_date": "2000-01-03",
        "build_time": "2000-01-04T12:00:00Z",
        "git_sha": "abc1234",
        "model_id": "test-org/test-model",
    }


def test_health_without_snapshot_says_so(client, tmp_path, monkeypatch):
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(tmp_path / "missing"))
    monkeypatch.delenv("LLM_MODEL", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "no_snapshot",
        "data_date": None,
        "build_time": None,
        "git_sha": None,
        "model_id": None,
    }


def test_health_never_exposes_secrets(client, tmp_path, monkeypatch):
    (tmp_path / "meta.json").write_text(json.dumps(SYNTHETIC_META))
    monkeypatch.setenv("TENORWISE_SNAPSHOT_DIR", str(tmp_path))
    secrets = {
        "LLM_API_KEY": "sk-synthetic-llm-secret",
        "FRED_API_KEY": "synthetic-fred-secret",
        "UPSTASH_REDIS_REST_TOKEN": "synthetic-redis-secret",
        "IP_HASH_SALT": "synthetic-salt-secret",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    body = client.get("/api/health").text

    for value in secrets.values():
        assert value not in body
