# Tenorwise

An interest-rate risk and hedging tool for a bank-style bond portfolio, with an
AI analyst whose every number is checked against the calculation engine before
it is shown.

**Live:** https://tenorwise.vercel.app. Deployed and smoke-tested on 2026-11-18; see [docs/deploy.md](docs/deploy.md).
**Measured results:** [RESULTS.md](RESULTS.md), generated from the evidence files.
**Build plan and progress log:** [PLAN.md](PLAN.md).

## A two-minute tour

1. **Overview.** A model bank bond portfolio built from public data: Treasury
   yields from FRED, and a sector mix based on BNY's Form 10-Q. It shows the
   market value, the unrealized loss and the DV01 (the dollars lost per 0.01%
   rise in rates). Select a scenario to jump to the hedges.
2. **Scenarios.** Seven rate moves, including a replay of 2022. Each splits the
   loss into what reaches AOCI (available-for-sale bonds, which hit equity) and
   what sits in held-to-maturity bonds and is not recognized. "Price scenario"
   sends any custom shock to the engine.
3. **Hedging.** Four swap hedges against seven scenarios. The scatter shows the
   trade-off: loss avoided against the carry given up.
4. **Analyst.** Ask a question in plain English.
   - Every number in the answer is a link to the tool, inputs and method that
     produced it.
   - If a number fails the check, the answer is blocked and only the engine's
     own figures are shown.
5. **Evidence.** Three language models answered the same 36 questions, graded
   against the engine, and the pricing code was compared with QuantLib.
6. **About.** Why this use case was chosen, the risk and control table, the
   model memo, the rollout plan and the decision log, rendered from
   `docs/strategy/`.

The mortgage pool is stylized and the IG corporates are a proxy. Nothing here is
any bank's actual holdings or investment advice.

## Run locally

Requirements: [uv](https://docs.astral.sh/uv/), Node 22.

```bash
uv sync                                   # Python 3.12 + dependencies
npm ci --prefix web                       # frontend dependencies
cp .env.example .env                      # then fill in your own keys

uv run python scripts/build_snapshot.py --fixture   # snapshot from the pinned data (offline)
# or: uv run --env-file .env python scripts/build_snapshot.py   # live FRED (needs FRED_API_KEY)
uv run --env-file .env uvicorn api.index:app --port 8000   # API on :8000
npm run dev --prefix web                  # frontend on http://localhost:5173 (proxies /api to :8000)
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

Model portfolio summary by sector and class (add `--positions` for all 38):

```bash
uv run python -m tenorwise.portfolio
```

Seven-scenario table (change in value, AOCI impact, HTM change, 12-month carry):

```bash
uv run python -m tenorwise.scenarios --by-sector
```

Hedging strategies and the strategy-by-scenario matrix (AOCI net of hedges, loss avoided, carry given up):

```bash
uv run python -m tenorwise.hedging
uv run python -m tenorwise.hedging --swap-spread-bp 25
```

After changing a contract model, regenerate the OpenAPI document and the TypeScript types:

```bash
uv run python scripts/export_openapi.py && npm run gen:types --prefix web
uv run python scripts/build_snapshot.py --pin   # refresh the pinned fixture snapshot
```

AI analyst (calls the configured model; paid):

```bash
uv run --env-file .env python -m tenorwise.agent ask "What would a repeat of 2022 do to AOCI?"
uv run --env-file .env python -m tenorwise.agent commentary
```

Evals (PLAN.md section 10). The dry run and the estimate are free; `run` is paid
and refuses to start unless `data/llm/prices.json` was re-read from Sail's pricing
page today:

```bash
uv run python -m tenorwise.evals dry-run     # full pipeline with a scripted oracle, no network
uv run python -m tenorwise.evals estimate    # cost estimate for 3 repeats x 36 questions per model
uv run --env-file .env python -m tenorwise.evals run --model zai-org/GLM-5.3 --max-cost 3.00
uv run --env-file .env python -m tenorwise.evals run --model deepseek-ai/DeepSeek-V4.1-Flash-1017 --max-cost 0.30
uv run --env-file .env python -m tenorwise.evals run --model moonshotai/Kimi-K3.1-Pro --max-cost 6.40
uv run python -m tenorwise.evals report      # docs/evidence/evals/summary.json and report.md
```

The HTTP endpoints need daily caps and a rate-limit store. For local development,
start the API with the in-process store (never used on Vercel):

```bash
RATE_LIMIT_BACKEND=memory AI_LIMIT_PER_IP_PER_DAY=10 AI_LIMIT_GLOBAL_PER_DAY=100 IP_HASH_SALT=local-dev \
  uv run --env-file .env uvicorn api.index:app --port 8000
```

Tests (the live LLM test is skipped unless `TENORWISE_LIVE=1`; this also runs the web build and the About page tests):

```bash
uv run pytest
npm test --prefix web            # unit and page tests (vitest)
npx playwright install chromium  # once, for the browser smoke tests
npm run test:e2e --prefix web    # every screen and analyst state, desktop and phone (Playwright)
```

After an engine or contract change, regenerate the browser-test fixtures and the design contract:

```bash
uv run python scripts/make_web_fixtures.py   # web/e2e/fixtures, from the real engine and agent loop
uv run python scripts/export_contract.py     # docs/api/contract.md, for the design handoff
```

Agreement with QuantLib (writes docs/evidence/quantlib_report.json):

```bash
uv run python scripts/quantlib_report.py
```

Provider probe (makes about 15 small paid calls to the LLM provider):

```bash
uv run --env-file .env python scripts/probe_llm.py
```

## Deploy

See [docs/deploy.md](docs/deploy.md): the Upstash database, the Vercel environment
variables, the firewall rule, the deploy command and the live smoke test. Every
deploy needs the owner's approval first (PLAN.md ground rule 10).

After new evals or a new QuantLib report, regenerate the results file:

```bash
uv run python scripts/make_results.py   # RESULTS.md; a test checks every number against the source files
```

## Documents

- [RESULTS.md](RESULTS.md): measured results only, generated
- [MODEL_CARD.md](MODEL_CARD.md): intended use, components, evidence and the human review procedure
- [NOTES.md](NOTES.md): the finance and the design, phase by phase
- [ASSUMPTIONS.md](ASSUMPTIONS.md) and [LIMITATIONS.md](LIMITATIONS.md)
- [docs/strategy/](docs/strategy/): opportunity map, effort sheet and timings, model memo, risks and controls, rollout plan (proposal), decision log; all rendered on the About page
- [docs/provider-probe.md](docs/provider-probe.md)
- [docs/evidence/evals/](docs/evidence/evals/): eval raw results, summary and report

## Data

US Treasury par yields come from FRED (series DGS1MO to DGS30, Federal Reserve
H.15 release). The mortgage rate is the Optimal Blue Mortgage Market Indices
(OBMMI™) 30-Year Fixed Rate Conforming Mortgage Index (OBMMIC30YF), via FRED.
The portfolio mix follows BNY's Form 10-Q for the quarter ended 30 September
2026 (Note 2); the positions are design choices, not BNY's holdings.

This product uses the FRED® API but is not endorsed or certified by the
Federal Reserve Bank of St. Louis. See the
[FRED® API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html).
