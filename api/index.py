"""Vercel entrypoint: exposes the FastAPI app as `app`.

vercel.json rewrites /api/* to this function. The app's routes carry the full
/api/... path. The repo root goes on sys.path so `tenorwise` is importable
both on Vercel and locally.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.api.app import app  # noqa: E402

__all__ = ["app"]
