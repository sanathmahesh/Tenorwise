"""Importing the deployed API app must not import pandas or QuantLib.

Ground rule 6: QuantLib is test-only and pandas stays off the request path.
This runs in a fresh interpreter, because pytest itself (or another test) may
already have imported pandas into the current process.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROBE = """
import sys
import api.index  # the Vercel entrypoint
from fastapi.testclient import TestClient

client = TestClient(api.index.app)
for path in ("/api/health", "/api/deploy-check"):
    client.get(path)

forbidden = {"pandas", "quantlib"}
loaded = sorted(m for m in sys.modules if m.split(".")[0].lower() in forbidden)
print(",".join(loaded))
"""


def test_api_app_imports_neither_pandas_nor_quantlib():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"forbidden modules loaded: {result.stdout.strip()}"
