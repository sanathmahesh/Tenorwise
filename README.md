# Tenorwise

An interest-rate risk and hedging tool for a bank-style bond portfolio, with an
AI analyst whose every number is checked against the calculation engine.

**Status:** Phase 3 (agency mortgage bonds, stylized) done. The build plan and progress log are in
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

Print the yield curve and its market data date (pinned FRED data, offline):

```bash
uv run python -m tenorwise.curve                    # base curve
uv run python -m tenorwise.curve --parallel 100     # +100 bp parallel shock
uv run python -m tenorwise.curve --key-rate 10 25   # +25 bp on the 10-year key rate
uv run --env-file .env python -m tenorwise.curve --live   # fetch today's curve from FRED
```

Price a bond and print its risk measures (coupon in percent, maturity in months):

```bash
uv run python -m tenorwise.analytics --coupon 4.5 --maturity-months 123
uv run python -m tenorwise.analytics --coupon 5 --maturity-months 120 --spread-bp 100 --face 1000000
```

Stylized mortgage-bond profile across rate shifts (price, duration, average life, CPR):

```bash
uv run python -m tenorwise.analytics.mbs_profile
uv run python -m tenorwise.analytics.mbs_profile --wac 6.5 --age 60 --remaining 300
```

Tests:

```bash
uv run pytest
```

Agreement with QuantLib (writes docs/evidence/quantlib_report.json):

```bash
uv run python scripts/quantlib_report.py
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

## Data

US Treasury par yields come from FRED (series DGS1MO to DGS30, Federal Reserve
H.15 release). The mortgage rate is the Optimal Blue Mortgage Market Indices
(OBMMI™) 30-Year Fixed Rate Conforming Mortgage Index (OBMMIC30YF), via FRED.

This product uses the FRED® API but is not endorsed or certified by the
Federal Reserve Bank of St. Louis. See the
[FRED® API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html).
