"""Filesystem locations, resolved relative to the repository root.

Works both locally and inside the Vercel function bundle, which keeps the
repository layout.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
