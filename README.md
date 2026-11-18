# Tenorwise

An interest-rate risk and hedging tool for a bank-style bond portfolio, with an
AI analyst whose every number is checked against the calculation engine.

**Status:** Phase 0 (foundations). The build plan and progress log are in
[PLAN.md](PLAN.md). There is no live link yet.

## Run locally

Requirements: [uv](https://docs.astral.sh/uv/), Node 22.

```bash
uv sync                                   # Python 3.12 + dependencies
npm ci --prefix web                       # frontend dependencies
cp .env.example .env                      # then fill in your own keys

uv run python scripts/build_snapshot.py   # writes the static JSON snapshot
uv run --env-file .env uvicorn api.index:app --port 8000   # API on :8000
npm run dev --prefix web                  # frontend on :5173 (proxies /api to :8000)
```

Tests:

```bash
uv run pytest
```

Provider probe (makes about 15 small paid calls to the LLM provider):

```bash
uv run --env-file .env python scripts/probe_llm.py
```

## Deploy (preview)

Every deploy needs the owner's approval first (PLAN.md ground rule 10).

```bash
npx vercel@65.12.1 deploy --build-env TENORWISE_GIT_SHA=$(git rev-parse --short HEAD)
```

Vercel runs `scripts/vercel_build.sh` (the Python snapshot, then the Vite
build) and packages `api/index.py` as the Python function.

## Documents

- [NOTES.md](NOTES.md): the finance and the design, phase by phase
- [ASSUMPTIONS.md](ASSUMPTIONS.md) and [LIMITATIONS.md](LIMITATIONS.md)
- [docs/strategy/decision-log.md](docs/strategy/decision-log.md)
- [docs/provider-probe.md](docs/provider-probe.md)
