#!/usr/bin/env bash
# Vercel build step (vercel.json "buildCommand"). Also runs locally.
#
# 1. Build the JSON snapshot with Python, using runtime dependencies only
#    (no dev group, so no QuantLib or pandas). The build environment lives in
#    /tmp so it is not swept into the function bundle.
# 2. Build the static frontend, which copies web/public/data/ into web/dist/.
set -euo pipefail

echo "== tool versions"
python3 --version || true
if command -v uv >/dev/null 2>&1; then
  UV="uv"
else
  echo "uv not on PATH; installing it with pip"
  python3 -m pip install --quiet --user uv
  UV="python3 -m uv"
fi
$UV --version

echo "== python snapshot build"
UV_PROJECT_ENVIRONMENT="${TMPDIR:-/tmp}/tenorwise-build-venv" \
  $UV run --frozen --no-dev python scripts/build_snapshot.py

echo "== frontend build"
npm run build --prefix web
