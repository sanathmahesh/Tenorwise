"""The implemented design (PLAN.md Phase 11): fixtures are current, and the browser smoke tests pass.

The type-check and build run in tests/api/test_web_build.py; the component tests in
tests/strategy. This runs Playwright over every screen and Analyst state at desktop
and phone width. Needs `npm ci --prefix web` and `npx playwright install chromium`.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"


def test_web_fixtures_match_what_the_engine_produces():
    spec = importlib.util.spec_from_file_location("make_web_fixtures", REPO / "scripts" / "make_web_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for rel, text in mod.render().items():
        path = mod.OUT / rel
        assert path.exists() and path.read_text(encoding="utf-8") == text, f"stale {rel}: run scripts/make_web_fixtures.py"


def test_browser_smoke_tests_pass():
    if not (WEB / "node_modules").exists():
        pytest.fail("web/node_modules missing: run `npm ci --prefix web` first")
    r = subprocess.run(["npx", "playwright", "test"], cwd=WEB, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-6000:] + r.stderr[-2000:]
