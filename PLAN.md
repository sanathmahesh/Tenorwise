# Tenorwise: build plan

This file is the complete brief for building Tenorwise. The repository contains nothing else yet, and there is no earlier conversation to draw on. Read all of it before you act. If you are resuming in a new session, read the progress log in section 17 to find the current phase.

Changes to this plan need my approval. When I approve one, edit this file and record the change in `docs/strategy/decision-log.md`.

## 1. Who this is for

I am a master's student and a strong AI engineer (agents, RAG, tool calling, eval harnesses). I have no finance background. I am applying for a graduate role on a bank's Asset-Side AI Strategy team, which applies AI to the bank's bond portfolio and lending. Tenorwise goes on my resume as a live link, and I will be asked to explain every part of it in an interview. Three consequences:

- When two designs both work, choose the one I can explain at a whiteboard.
- Explain each finance concept in plain English the first time it appears, in NOTES.md and in your messages to me. Do not explain AI engineering.
- Nothing is described as measured unless it was measured. A wrong number on my resume is worse than a missing one.

## 2. What Tenorwise is

An interest-rate risk and hedging tool for a bank-style bond portfolio, with an AI analyst on top. It answers: if interest rates move, how much does the portfolio lose, and which hedge is worth its cost?

It must do nine things:

1. **Yield curve.** Pull US Treasury par yields from FRED, bootstrap a zero curve, interpolate.
2. **Bond analytics.** Price, yield, modified and effective duration, convexity, DV01, key-rate durations at 2, 5, 10 and 30 years.
3. **Agency mortgage bonds.** A stylized pass-through with a refinancing-incentive prepayment curve, enough to show negative convexity and extension risk, labelled stylized.
4. **Portfolio.** A model book of about $10B across Treasuries, agency mortgage bonds, agency debt and investment-grade corporates, each position tagged available-for-sale (AFS) or held-to-maturity (HTM), with the mix based on BNY's most recent 10-Q and cited.
5. **Scenarios.** Parallel shifts of +/-100 and +/-200 bp, a bear steepener, a bull flattener and a replay of 2022, reporting change in market value, impact on AOCI (AFS positions only) and 12-month carry.
6. **Hedging.** Pay-fixed swaps at 2, 5 and 10 years. Compare unhedged, 50% DV01 hedge, full DV01 hedge and key-rate-matched hedge, showing loss avoided against carry given up in each scenario.
7. **AI analyst.** A tool-calling agent whose tools wrap the engine. It answers plain-English questions and drafts a one-page portfolio commentary.
8. **Verification.** Code that extracts every number from the agent's text and matches it to a tool result within a stated tolerance. Any mismatch blocks the answer. In the interface each number links to the calculation behind it.
9. **Evals.** At least 30 questions whose correct answers are computed directly from the engine, reporting accuracy, latency and cost per question.

## 3. Ground rules

Copy this section into CLAUDE.md in Phase 0, under a first line that says to read PLAN.md and its progress log before doing anything.

1. The language model never does arithmetic. Every figure comes from deterministic, tested code.
2. Never invent or silently substitute data. If a source is unavailable, a figure cannot be confirmed, or a live document disagrees with this plan, stop and ask me. A modelling assumption is allowed only if it is written in ASSUMPTIONS.md and labelled wherever its result is shown.
3. Do not change the scope, in either direction, without asking.
4. Build phase by phase. Write the phase's tests first, see them fail, then implement. Commit after each phase. Then stop, show me how to run it, and wait for my go-ahead.
5. Keep ASSUMPTIONS.md, LIMITATIONS.md, NOTES.md and `docs/strategy/decision-log.md` current, in the same commit as the change that affects them.
6. QuantLib is a test-only dependency used as an independent benchmark. It must not be importable from the deployed app. pandas may be used in the data pipeline and eval reporting but must not be imported on the request path.
7. Design for serverless: nothing held in memory between requests, no writes to local disk at runtime.
8. Secrets live only in environment variables. Never print, commit or log a key, and never let one reach the web bundle.
9. This repo is standalone. It shares nothing with any other project: new Vercel project, new Upstash database, no imported code.
10. Ask before any outward-facing or paid action: the first push to GitHub, every Vercel deploy, creating the Upstash database, and any LLM spend beyond single smoke-test calls. Give me a cost estimate before running evals.
11. Report faithfully. Show failing tests with their output. Never loosen a tolerance to make a test pass; report the measured gap and ask.
12. Anything stylized is labelled stylized in the code, the API and the interface.

## 4. Facts checked on 17 November 2026

These were read from the sources below. Sources change, and some were transcribed by a research agent, so open each one yourself at the phase that uses it. If what you find differs, stop and tell me.

### Sail Research (the inference provider; not the Claude API)

- Docs: https://docs.sailresearch.com/llms.txt, and the pages `models.md`, `pricing.md`, `support.md`, `migrate.md`, `service-tiers.md`, `retries.md` under the same host.
- OpenAI-compatible. Base URL `https://api.sailresearch.com/v1`, header `Authorization: Bearer <key>`. Use `POST /v1/chat/completions`.
- Chat Completions supports function tools in the standard format, `tool_choice` (none, auto, required, specific), `response_format` (text, json_object, json_schema) and streaming.
- Rejected or unsupported on Chat Completions: `max_tokens` (use `max_completion_tokens`), `functions`, `function_call`, `n` other than 1, `seed`, `stop`, `logprobs`, `frequency_penalty`, `presence_penalty`, `logit_bias`.
- Service tiers: the default is `asap` (no queueing, recommended for chat). `balanced` may queue the first turn for up to 5 minutes. The docs exclude only tools of type `custom` from `asap`; ordinary function tools appear to be allowed, but no page says so directly. The response reports the tier that served it in `service_tier`.
- Usage fields: `prompt_tokens`, `completion_tokens`, `total_tokens`. The inner fields of `prompt_tokens_details` are not documented.
- Errors: 429, 503 `model_capacity_unavailable` and 503 `service_overloaded` are refused before inference and are safe to retry after `Retry-After` with backoff (`service_overloaded` added 2026-11-17 from `retries.md`; decision log D-014). Other 5xx and timeouts are uncertain. Disable SDK auto-retries and implement retries yourself as `retries.md` describes.
- There is no per-model capability matrix and no published context window. `GET /v1/models` returns IDs only.
- Sail retires models at short notice (the changelog announced one retirement with a week's warning), so the model ID must be configuration.
- GLM-5.3 returns HTTP 400 if reasoning effort is set to none.

Models to evaluate, with ASAP list prices in US dollars per million tokens:

| Model ID | Input | Cached input | Output |
|---|---|---|---|
| `zai-org/GLM-5.3` | 0.98 | 0.18 | 3.08 |
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | 0.09 | 0.006 | 0.30 |
| `moonshotai/Kimi-K3.1-Pro` | 1.50 | 0.20 | 10.00 |

### Vercel (free Hobby plan)

- Docs on vercel.com: `/docs/functions/runtimes/python`, `/docs/frameworks/backend/fastapi`, `/docs/functions/limitations`, `/docs/vercel-firewall/vercel-waf/rate-limiting`, `/docs/services`.
- Python 3.12 by default. Dependencies come from `pyproject.toml` (with or without `uv.lock`) or `requirements.txt`. Python functions may be 500 MB uncompressed.
- Hobby: 300 s maximum duration, 2 GB memory, runtime logs kept 1 hour.
- A file in `/api` that defines `app` becomes a function. Vercel also offers "Services" (beta) for a frontend and backend in one project.
- Hobby allows one firewall rate-limit rule per project (per IP, fixed window of 10 s to 10 min).
- Not confirmed: whether a Python script can run in the build step of a Vite-plus-`/api` project, and whether files it writes are bundled into the function. Phase 0 exists partly to prove this.

### BNY 10-Q for the quarter ended 30 September 2026 (filed 30 October 2026)

- PDF: https://www.bny.com/content/dam/bnymellon/documents/pdf/investor-relations/form-10-q-3q26.pdf
- EDGAR: https://www.sec.gov/Archives/edgar/data/1390777/000139077726000120/bk-20260930.htm (sec.gov may refuse automated requests; use the PDF).
- "Note 2 - Investment securities", page 52, in $ millions:

| Category | AFS (fair value) | HTM (amortized cost) |
|---|---|---|
| US Treasury | 30,088 | 5,142 |
| Non-US government | 27,071 | 5,158 |
| Agency RMBS | 21,491 | 29,178 |
| Foreign covered bonds | 8,163 | 526 |
| CLOs | 7,264 | 1,856 |
| Agency commercial MBS | 6,183 | 2,589 |
| Non-agency commercial MBS | 1,798 | 0 |
| US government agencies | 1,494 | 2,272 |
| Non-agency RMBS | 1,486 | 0 |
| Other ABS | 214 | 0 |
| Other debt securities | 0 | 11 |
| **Total** | **105,252** | **46,732** |

- Same note, maturity table: yield on amortized cost is 3.57% for AFS and 2.58% for HTM.
- Note 14, page 79: "$61.1 billion designated par value of available-for-sale securities were hedged with interest rate swaps designated as fair value hedges that had notional values of $60.9 billion."

### US model risk management guidance

- SR 11-7 is no longer current. On 17 April 2026 the agencies issued revised guidance: Federal Reserve SR 26-2 (https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm, text at https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf), OCC Bulletin 2026-13, FDIC FIL-15-2026.
- Footnote 3: "Generative AI and agentic AI models are novel and rapidly evolving. As such, they are not within the scope of this guidance."
- It defines a model as "a complex quantitative method, system, or approach that applies statistical, economic, or financial theories to process input data into quantitative estimates", and excludes "simple arithmetic calculations" and "deterministic rule-based processes and software where there are no statistical, economic, or financial theories underpinning their design or use".
- Its vocabulary: model materiality, effective challenge, conceptual soundness, outcomes analysis, ongoing model monitoring, model inventory, model limitations, vendor and other third-party products.
- NIST AI 600-1 (Generative AI Profile, July 2024) is a non-supervisory reference that does cover generative AI.

### FRED

- API: https://api.stlouisfed.org/fred/series/observations. Read the API terms of use and include the attribution notice they require.
- Missing observations are returned as ".".

### One accounting point to confirm before Phase 6

Under US GAAP (ASC 815), interest-rate risk on held-to-maturity debt securities cannot be the hedged risk in a hedge accounting relationship. This was stated from memory, not checked. The hedging design in section 7 depends on it, so confirm it from a primary or authoritative source.

## 5. Architecture and stack

- **Backend:** Python 3.12, FastAPI, numpy, scipy, pandas, pydantic, pytest, managed with uv and `pyproject.toml`. QuantLib only in the dev group.
- **Frontend:** React, Vite, TypeScript, in `web/`.
- **Inference:** Sail, behind one provider interface configured by three environment variables: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. No Sail specifics outside that module.
- **Hosting:** one Vercel project. Static frontend, plus FastAPI as a Python function at `api/index.py` with `/api/*` rewritten to it. If that layout cannot do what Phase 0 requires, tell me before trying Services.
- **Data flow:** at build time a script fetches FRED, runs the engine and writes static JSON (curve, portfolio, scenario grid, hedges). The frontend reads those files directly. The function loads the same files read-only and computes only custom scenarios and agent tool calls.
- The interface shows the market data date everywhere.

Environment variables: `FRED_API_KEY` (build only), `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `IP_HASH_SALT`, `AI_LIMIT_PER_IP_PER_DAY`, `AI_LIMIT_GLOBAL_PER_DAY`.

I already have a FRED key, a Sail key with a card on file, a Vercel Hobby account and a GitHub account. Ask me to put the keys in `.env`; never ask me to paste one into the chat.

Repo layout:

```
PLAN.md  CLAUDE.md  NOTES.md  ASSUMPTIONS.md  LIMITATIONS.md
MODEL_CARD.md  RESULTS.md  README.md
pyproject.toml  uv.lock  vercel.json  .env.example
api/index.py              Vercel entrypoint, exposes the FastAPI app
tenorwise/
  curve/                  FRED client, bootstrap, interpolation, shocks
  instruments/            bond, mortgage pass-through, swap
  analytics/              duration, convexity, DV01, key-rate durations
  portfolio/              positions, aggregation, amortized cost
  scenarios/              definitions, revaluation, carry
  hedging/                strategies and sizing
  snapshot/               build-time pre-compute, JSON schemas
  agent/                  provider, tools, ledger, loop, verifier
  api/                    routes, rate limit
  evals/                  questions, gold answers, runner, report
data/sources/             BNY table transcription with citation
data/fixtures/            pinned FRED data for tests and evals
scripts/                  build_snapshot, probe_llm, run_evals, make_results
tests/                    unit, benchmark (QuantLib), agent, api
web/                      Vite + React + TypeScript
docs/strategy/            six strategy artifacts (Markdown)
```

## 6. Engine specification

Every choice in this section and the next is a simplifying assumption. Copy each into ASSUMPTIONS.md in plain English, and list what it leaves out in LIMITATIONS.md. State sign conventions once in NOTES.md and use them everywhere.

### Time

All times are year fractions. Maturities are whole months; `t = months / 12`. No day-count conventions, holidays or settlement lag.

### Curve

- Inputs: par yields at 11 tenors from FRED series DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS3, DGS5, DGS7, DGS10, DGS20, DGS30.
- Use the most recent date on which all 11 have values. If that date is more than 7 days before the build, fail the build. Never fill forward.
- Treat par yields as semiannual bond-equivalent yields.
- For tenors of 0.5 years and under, the instrument is a single payment: `DF(T) = 1 / (1 + y*T)`.
- For tenors of 1 year and over, the instrument is a par bond paying `y/2` every half year. Working outward one tenor at a time, solve (scipy `brentq`) for the continuously compounded zero rate at that tenor such that the bond prices to exactly 100, with zero rates between curve points on a straight line in time.
- Interpolation: linear in zero rate between curve points, flat beyond the ends. `DF(t) = exp(-z(t)*t)`.

### Shocks

- A shock is a number of basis points added to each of the 11 par yields, after which the curve is rebuilt from scratch. Every scenario, every effective-duration bump and every key-rate bump uses this one mechanism.
- Floor shocked par yields at 0% and flag it in the output if the floor binds.
- Key-rate shocks are tents over tenor at 2, 5, 10 and 30 years:
  - The 2-year tent is 1 at tenors up to 2 and falls linearly to 0 at 5.
  - The 5-year tent rises from 0 at 2 to 1 at 5 and falls to 0 at 10.
  - The 10-year tent rises from 0 at 5 to 1 at 10 and falls to 0 at 30.
  - The 30-year tent rises from 0 at 10 to 1 at 30 and beyond.
  - The four tents sum to 1 at every tenor.

### Fixed-rate bonds

- Semiannual coupons, principal at maturity, cash flows at T, T-0.5, ... while positive. No call features, no floating rates.
- Dirty price = sum of `CF * exp(-(z(t) + s) * t)`, where `s` is a constant spread for the position's sector.
- Accrued interest is the coupon times the fraction of the current half-year elapsed. Clean = dirty - accrued.
- Yield: the semiannually compounded rate that reproduces the dirty price.
- Macaulay duration, modified duration (`Macaulay / (1 + y/2)`) and convexity from the yield.
- Effective duration and convexity: reprice under parallel shocks of +/-25 bp.
- DV01: reprice under +/-1 bp, in dollars per basis point.
- Key-rate durations and key-rate DV01s: reprice under each tent.

### Agency mortgage pass-through (stylized)

- One pool is a level-payment fixed-rate loan with a gross coupon (WAC), a net coupon of WAC minus 0.50%, a remaining term in months and an age.
- Each month: scheduled payment from the level-payment formula on the remaining balance and term; interest; scheduled principal; prepayment = `SMM * (balance - scheduled principal)`, with `SMM = 1 - (1 - CPR)^(1/12)`. The investor receives net interest plus all principal.
- `CPR = ramp * (CPR_min + (CPR_max - CPR_min) / (1 + exp(-k * (incentive - x0))))`, where:
  - incentive = WAC - mortgage rate, in percentage points;
  - mortgage rate = the scenario's 10-year par yield + a fixed mortgage spread;
  - mortgage spread = latest FRED OBMMIC30YF (Optimal Blue 30-year fixed conforming mortgage index) minus DGS10 on the same date (changed from MORTGAGE30US on 2026-11-17, decision log D-031: Freddie Mac's terms forbid publishing its data or derived products without a licence);
  - ramp = min(1, age in months / 30).
- Starting parameters: CPR_min 6%, CPR_max 40%, k = 3, x0 = 1.0. These are illustrative, not calibrated; say so wherever they appear.
- Valuation is static: project cash flows once under the scenario curve and discount them. No rate volatility, no option-adjusted spread, no burnout, no seasonality.
- Report price, effective duration, effective convexity, weighted average life and CPR.

### Portfolio

- Four sectors: Treasuries, agency mortgage bonds, agency debt, investment-grade corporates. Each position is AFS or HTM.
- Mix: transcribe BNY's Note 2 table into `data/sources/` with the URL, page and filing date, re-reading the filing yourself. Map it as follows:

| Model sector | BNY lines |
|---|---|
| Treasuries | US Treasury |
| Agency mortgage bonds | Agency RMBS |
| Agency debt | US government agencies + agency commercial MBS |
| IG corporates (proxy) | Foreign covered bonds + non-agency commercial MBS + non-agency RMBS + other ABS + other debt |
| Excluded | Non-US government (needs foreign curves) and CLOs (floating rate) |

- Expected weights, to be recomputed from the filing: Treasuries 31.8% (AFS 27.2 / HTM 4.6), agency mortgage 45.8% (19.4 / 26.4), agency debt 11.3% (6.9 / 4.4), IG corporates 11.0% (10.5 / 0.5).
- BNY holds almost no corporate bonds, so the corporate sleeve is a labelled stand-in for its fixed-rate credit holdings. Say this in the interface and in NOTES.md.
- About 40 positions. Propose the list (coupons, maturities, mortgage pool parameters, sector spreads, book yields) and show it to me for approval before building on it. These are design choices, not data; label them.
- Book yield is the yield at which the bank is assumed to have bought the position. Choose book yields so the AFS and HTM averages sit near BNY's disclosed 3.57% and 2.58%, and report how close they are.
- Amortized cost = remaining cash flows discounted at the book yield. Unrealized gain or loss = market value - amortized cost.
- Scale positions so total amortized cost is $10,000M.

### Scenarios

Seven presets, all instantaneous shocks to par yields, after which the curve is held still:

| Scenario | Shock |
|---|---|
| Parallel | +100, -100, +200, -200 bp |
| Bear steepener | +25 bp up to 2y, +50 at 5y, +75 at 10y, +100 at 30y |
| Bull flattener | -25 bp up to 2y, -50 at 5y, -75 at 10y, -100 at 30y |
| 2022 replay | Per-tenor change in the FRED par yields between 2021-12-31 and 2022-12-30, applied to today's curve |

- The steepener and flattener are the tents scaled by those amounts.
- Sector spreads and the mortgage spread do not move in any scenario.
- Outputs per position, sector and class:
  - change in market value;
  - AOCI impact = change in value of AFS positions only, pre-tax;
  - the HTM change, reported separately as not recognized in the accounts;
  - 12-month carry.
- Carry is gross interest income: amortized cost times book yield over 12 months (prorated if the bond matures sooner). For mortgage pools the balance runs down with the scenario's prepayments. No funding cost, no reinvestment of cash received.

## 7. Hedging specification

- Swap curve = Treasury zero curve + a flat spread, default 0 bp, because no free SOFR swap curve is available. Record it as an assumption, show it in the interface, and include a test showing how hedge carry moves if the spread is +/-25 bp.
- Pay-fixed swaps at 2, 5 and 10 years, fixed leg semiannual.
  - Par rate `K = (1 - DF(T)) / (0.5 * sum of DF(t_i))`.
  - Value to the fixed payer per unit notional = `(1 - DF(T)) - K * 0.5 * sum of DF(t_i)`.
  - Swaps are entered at the base curve at par and revalued on the shocked curve.
- 12-month swap carry = `notional * (floating rate - K)`, where the floating rate is the 3-month rate implied by the scenario's swap curve, held constant.
- Hedges are sized against the AFS book only, because AFS losses are the ones that reach AOCI and (subject to the check in section 4) HTM cannot receive hedge accounting for rate risk. Treat the swaps as perfectly effective fair-value hedges, so AOCI net of hedges = AFS change + swap gain or loss.
- Strategies, sized once at the base curve and never rebalanced:

| Strategy | Construction |
|---|---|
| Unhedged | No swaps |
| 50% DV01 | One 5-year swap offsetting half the AFS DV01 |
| Full DV01 | One 5-year swap offsetting all of it |
| Key-rate-matched | 2, 5 and 10-year swaps solving a 3x3 system so the hedged AFS book has zero key-rate DV01 at 2y, zero at 5y, and zero at 10y and 30y combined |

- In the key-rate hedge the 30-year bucket is hedged by proxy with the 10-year swap. List the leftover 10s-30s risk in LIMITATIONS.md.
- Per strategy and scenario: swap notionals and fixed rates; change in securities value; swap gain or loss; net change; AOCI net of hedges; loss avoided (= swap gain or loss); carry given up (= minus swap carry); net carry.

## 8. Snapshot and API

- `scripts/build_snapshot.py` fetches FRED, builds everything and writes the JSON files below to `web/public/data/v1/` and to a folder the function can read.
- Serialization is deterministic (sorted keys, fixed rounding).
- If FRED fails, the build fails; the previous deployment stays live.
- A pinned fixture snapshot in `data/fixtures/` is used by tests and evals so results are reproducible.
- Define every response as a pydantic model, export the OpenAPI schema and generate the TypeScript types from it.

Endpoints:

| Method and path | Purpose |
|---|---|
| `GET /api/health` | Status, data date, build time, git SHA, model ID |
| `POST /api/scenario` | Custom parallel shift (-300 to +300 bp) or custom key-rate shocks |
| `POST /api/agent/ask` | `{question, history}` |
| `POST /api/agent/commentary` | One-page commentary draft |

### Response shapes

I am designing the interface in Claude Design against these field names, so treat them as the contract. If you need to change one, tell me first so I can update the design. All money is in US dollars and rates are in percent.

```
meta.json
  data_date, build_time, git_sha, fred_series[], llm_model, assumptions[]

curve.json
  data_date
  points[]: tenor_years, par_yield, zero_rate, discount_factor

portfolio.json
  summary: market_value, amortized_cost, unrealized, eff_duration,
           convexity, dv01, key_rate_dv01{2,5,10,30}
  by_sector[], by_class[]: same fields plus weight
  positions[]: id, name, sector, class, face, coupon, maturity_years,
               book_yield, price, market_value, amortized_cost, unrealized,
               eff_duration, mod_duration, convexity, dv01,
               key_rate_dv01{2,5,10,30}
  source: citation text and URL

mbs.json
  profile[]: shift_bp, price, eff_duration, avg_life_years, cpr
  comparison_treasury[]: shift_bp, price
  s_curve[]: incentive_pct, cpr

scenarios.json
  scenarios[]: id, name, description, shock_bp_by_tenor[],
               total{delta_mv, delta_mv_pct, aoci_impact,
                     htm_unrecognized, carry_12m},
               by_sector[], by_class[], shocked_curve[]

hedges.json
  strategies[]: id, name, swaps[]{tenor_years, notional, fixed_rate, dv01},
                key_rate_dv01_after{2,5,10,30}
  grid[]: strategy_id, scenario_id, securities_delta_mv, swap_pnl,
          net_delta_mv, aoci_net, loss_avoided, carry_given_up, net_carry

methods.json
  methods{method_id: {name, plain_english, formula, notes_anchor}}

POST /api/scenario  ->  one scenarios[] entry plus its hedges grid rows

POST /api/agent/ask and /api/agent/commentary
  status: answered | cannot_answer | blocked | error
  answer_md: prose with number tags, e.g. "falls by $412.3M[[v12]]"
  sections[] (commentary only): heading, body_md
  values{v12: {value, unit, display, label, tool, args, method, inputs}}
  checks[]: token, tag, passed, reason
  trace[]: tool, args, ms
  usage: model, served_tier, llm_calls, prompt_tokens, completion_tokens,
         cost_usd, latency_ms
  fallback (blocked only): table of raw engine results
  data_date

evidence.json
  models[]: id, accuracy, block_rate, verified_but_wrong_rate,
            latency_p50_ms, latency_p95_ms, cost_per_question_usd, runs
  questions[]: id, category, text, results{model_id: pass|fail|blocked}
  quantlib[]: measure, instruments, max_abs_diff, unit
```

## 9. AI analyst and verification

### Provider

- One interface, one OpenAI-compatible implementation, plus a scripted fake provider for tests. No network in unit tests.
- Send `max_completion_tokens`, not `max_tokens`. Do not send `seed`, `stop` or penalties.
- Record the served tier and token usage from every response.

### Tools

All tools are read-only and wrap the engine.

- `get_curve`, `get_portfolio_summary`, `get_positions`, `run_scenario`, `compare_hedges`, `get_hedge`, `get_mbs_profile`, `get_methodology`.
- `derive`: a calculator for sums, differences, ratios and percentage changes. Its operands are value IDs from earlier tool results. This is how the model obtains any figure the other tools do not return directly, so it never does arithmetic itself.
- `submit_answer(status, answer_md)`, with status `answered` or `cannot_answer`, and `submit_commentary(sections)`. The final answer is delivered as a tool call so that tool calling is the only structured output the design relies on.

### Ledger

- Every numeric value a tool returns gets an ID (v1, v2, ...), a unit, a canonical display string (for example "-$412.3M"), a label, and its provenance: tool, arguments, method ID and input IDs.
- Tool arguments and fixed descriptors (tenors, shock sizes, hedge ratios, the 12-month horizon, dates) are recorded as context numbers.
- The ledger lives for one request. Earlier turns are passed as text for context only; to state a number, the model must fetch it again.

### Answer format

The model writes each number followed by its tag: "falls by $412.3M[[v12]]". The system prompt tells it to copy the display string.

### Verifier

- Extract every numeric token from the text: signs, parentheses, currency, thousands separators, decimals, magnitude words and suffixes (K, M, B, million, billion), and units (%, bp, years, months).
- A tagged number passes if the tag exists, the unit is compatible, and either the text equals the canonical display, or the printed number is the cited value correctly rounded to the printed precision and within 0.5% of it. An explicit sign must match. This is the stated tolerance; print it in MODEL_CARD.md and in the interface.
- An untagged number passes only if it equals a context number.
- Anything else fails, and one failure blocks the whole answer.
- On failure, return the failed checks to the model as the tool result of `submit_answer` and allow one repair attempt. If that also fails, respond with status `blocked`, no prose, and a deterministic table of the raw tool results. Unverified text is never returned; test this.
- Record in LIMITATIONS.md that verification proves each number came from the engine and was copied correctly, not that the sentence around it is right.

### Loop and limits

- At most 6 model calls per request, a per-call timeout, a question length cap, and retries only for 429 and 503 capacity errors (`model_capacity_unavailable`, `service_overloaded`) with backoff.
- Commentary: about 400 words in fixed sections (positioning, rate sensitivity, scenario results, hedging trade-off, caveats), verified the same way, and always shown with "Draft, requires human review".
- Rate limits on the AI endpoints: one Vercel firewall rule per IP (I will create it in the dashboard from your instructions), plus per-IP and global daily caps in Upstash Redis keyed by a salted hash of the IP. If Redis is unreachable, the AI endpoints refuse; the rest of the app is unaffected. Propose the cap values and ask me.
- Log request ID, model, tier, tokens, latency and verification outcome. Do not log question text.

## 10. Evals

- 36 questions in six groups:
  - curve and portfolio lookups;
  - single-scenario results;
  - hedge comparisons;
  - derived figures that need the `derive` tool;
  - mortgage behaviour;
  - questions the analyst should decline (figures the engine cannot produce, requests to estimate without tools, positions that do not exist, requests for investment advice).
- Each question has a gold function that calls the engine directly, not the agent tools, and returns the required values with units.
- Grading is deterministic, with no LLM judge. An answer is correct if its status matches and every required gold value appears among its verified cited values under the verifier's tolerance.
- Report per model:
  - accuracy;
  - verification block rate before and after the repair attempt;
  - the rate of answers that passed verification but were wrong (the failure the verifier cannot catch);
  - latency p50 and p95, measured from the eval machine and labelled as such;
  - cost per question from token usage at list prices for the served tier, re-read from Sail's pricing page on the day and dated. If usage does not report cached tokens, say the cost is an upper bound.
- Models: `zai-org/GLM-5.3`, `deepseek-ai/DeepSeek-V4.1-Flash-1017` and `moonshotai/Kimi-K3.1-Pro`, each only if it passed the Phase 0 probe.
- Three repeats per model, because Sail offers no seed. Report the mean and range.
- Save raw results as JSON. Every reported figure is generated from those files by a script.

## 11. Strategy artifacts

This role is AI strategy, so the project must show judgment about where and how AI is used. Write these in plain English in `docs/strategy/`, render them on an About page from the same files, and explain the reasoning behind each in NOTES.md so I can defend it.

1. **Opportunity map.** 8 to 10 workflows of a bank's investment and lending teams, scored on value, feasibility and risk with a stated rubric and a reason per score, ending with why this use case was chosen. The scores are reasoned judgments from public sources, not measurements or practitioner interviews; say so on the page. Draft it, then walk me through it so I can challenge and own it.
2. **Manual against tool-assisted effort**, using only timings I record myself. Write the task sheet and an empty timings CSV, then stop and wait for me. Never enter or estimate a timing. Until the CSV has data the page says the timings are not yet recorded. State that the operator is one non-expert.
3. **Model recommendation memo** from the eval results: accuracy, latency and cost per task for each model tested, and a recommendation with its trade-off.
4. **Risk and control table.** Each failure mode, the control that catches it, and the evidence that the control works (a named test, benchmark or eval figure). Use SR 26-2 vocabulary, after reading the guidance yourself. Be exact about scope: the pricing engine applies financial theory to produce estimates, so describe it in the guidance's terms; the LLM layer is outside the guidance by footnote 3, so say that, and describe its controls as governance practices, citing NIST AI 600-1 where it helps. Do not claim the project is validated or compliant.
5. **Rollout plan.** Pilot group, human review step, what gets logged, and what would trigger a rollback. Mark it as a proposal that has not been executed.
6. **Decision log.** The main design choices with the alternatives rejected and why. Start it in Phase 0 and add to it every phase.

## 12. Documents you maintain throughout

- **NOTES.md**, one section per phase: the finance concepts in plain English; how the code implements them, with file references; why this design and what was rejected; what would break it; and five to eight interview questions with short model answers.
- **ASSUMPTIONS.md**: every simplifying assumption, where it is used, and its likely effect.
- **LIMITATIONS.md**: what the tool cannot tell you and why.

## 13. Phases

For each phase: write the listed tests first, implement, run the whole suite, update the documents, commit, update the progress log in section 17, then stop and send me the phase report described in section 15.

### Phase 0. Foundations, provider probe, skeleton deploy

- Initialize git. Create CLAUDE.md from section 3, the document skeletons, `pyproject.toml`, `.env.example`, a FastAPI app with `/api/health`, and a placeholder Vite page.
- `scripts/probe_llm.py`: for each of the three models, test a plain completion, a function-tool round trip, `tool_choice` "required", a `json_schema` response, the usage fields and the served tier. Save the raw findings to `docs/provider-probe.md`. If a model fails tool calling, or function tools do not run on the `asap` tier, stop and ask me.
- Skeleton deploy to a Vercel preview, after asking: a build step runs a Python script that writes a JSON file; the page shows it and the function returns it; numpy and scipy are installed in the function.
- Tests: health endpoint; importing the API app imports neither pandas nor QuantLib.
- I can run: the probe script and the preview URL.

### Phase 1. Yield curve

- Builds: FRED client, fixture, bootstrap, interpolation, shocks, a small CLI.
- Tests:
  - the parser handles "." and picks the latest complete date;
  - stale data fails;
  - every input par instrument reprices to 100 within 1e-8;
  - a flat par curve gives a flat zero curve at the equivalent continuous rate from 6 months out, and at 1 and 3 months each zero rate matches its own simple-interest instrument (reworded 2026-11-17, decision log D-023);
  - discount factors are positive and decreasing;
  - interpolation is exact at curve points and linear between;
  - a zero shock returns the same curve;
  - shocked par bonds reprice to 100 on the shocked curve;
  - the four tents sum to 1;
  - zero rates at the curve points match a QuantLib piecewise linear-zero curve built from equivalent instruments.
- I can run: a command that prints the curve and its data date.

### Phase 2. Bond analytics

- Tests:
  - a par bond prices to 100;
  - a zero-coupon bond's Macaulay duration equals its maturity;
  - price to yield to price round-trips;
  - clean plus accrued equals dirty;
  - formula DV01 matches bump-and-reprice within 0.1% on a flat par curve; on the real curve, the gap equals the bond's own-yield move per 1 bp of par yields, within 0.1% (reworded 2026-11-17, decision log D-024);
  - duration plus convexity predicts a 100 bp reprice closely;
  - convexity is positive;
  - the four key-rate durations sum to effective duration within 0.5%;
  - a 2-year bond's key-rate duration sits in the 2-year bucket;
  - price, yield, Macaulay and modified duration and convexity match QuantLib on the same zero curve across a grid of coupons from 0% to 8% and maturities from 6 months to 30 years, including off-cycle maturities.
- Build the QuantLib side with conventions that reduce to mine (30/360, no calendar, no settlement lag) and write the measured maximum differences to a JSON report.
- I can run: a command that prices any bond and prints its risk measures.

### Phase 3. Agency mortgage bonds

- Tests:
  - at zero prepayment the payment is constant and the balance ends at zero;
  - total principal equals the starting balance at any speed;
  - discounting at the net coupon (monthly) gives par at any speed;
  - CPR and SMM round-trip;
  - CPR rises with incentive and stays within its bounds;
  - average life at +200 bp is above base, which is above -200 bp;
  - effective convexity is negative for a pool near current rates (WAC equal to the current mortgage rate, discounted at the spread that prices it at par) and positive for a Treasury of similar duration (reworded 2026-11-17, D-032);
  - for that pool, the gain at -100 bp is smaller than the loss at +100 bp;
  - effective duration rises as rates rise from -100 to +50 bp, where prepayments respond; beyond that the pool behaves like a fixed bond and this is documented, not tested as rising (reworded 2026-11-17, D-032).
- I can run: a table of price, duration, average life and CPR across shifts.

### Phase 4. Portfolio

- Re-read the BNY filing, transcribe, map, and get my approval of the position list.
- Tests:
  - transcribed lines sum to BNY's stated totals;
  - sector and class weights match the mapping within 0.1 percentage points;
  - total amortized cost is $10,000M within 0.5%;
  - a bond bought at par has amortized cost equal to face;
  - portfolio value and DV01 equal the sums of positions;
  - portfolio duration is the value-weighted average;
  - average AFS and HTM book yields are reported against BNY's.
- I can run: a portfolio summary by sector and class.

### Phase 5. Scenarios

- Tests:
  - a zero shock changes nothing;
  - a +/-1 bp shift matches DV01 within 1%;
  - change in value is ordered across -200, -100, +100, +200;
  - AOCI impact equals the AFS change and excludes HTM;
  - the mortgage sleeve gains less at -100 than it loses at +100;
  - the steepener loses and the flattener gains;
  - the 2022 shock equals the fixture differences tenor by tenor;
  - bullet-bond carry equals amortized cost times book yield;
  - mortgage carry falls in rallies;
  - the zero floor is flagged when it binds.
- I can run: the seven-scenario table.

### Phase 6. Hedging

- Confirm the ASC 815 point first.
- Tests:
  - a new swap is worth zero;
  - the fixed payer gains when rates rise;
  - swap DV01 matches bump-and-reprice;
  - par rates and values match QuantLib under equivalent conventions;
  - the 50% hedge leaves half the AFS DV01 and the full hedge leaves about none;
  - the full DV01 hedge is near flat for +/-10 bp parallel shifts but leaves a residual loss in the bear steepener;
  - the key-rate hedge zeroes the 2y and 5y buckets and the 10y-plus-30y total, and its steepener residual is smaller than the full DV01 hedge's;
  - at +/-200 bp the full hedge's residual has the sign implied by the AFS book's convexity;
  - loss avoided and carry given up reconcile to hedged minus unhedged;
  - the swap-spread sensitivity test.
- I can run: the strategy-by-scenario matrix.

### Phase 7. Snapshot, API, placeholder interface

- Tests:
  - every JSON file validates against its schema;
  - two builds from the same fixture are byte-identical;
  - `/api/scenario` equals the engine and rejects out-of-range input;
  - the request path imports neither pandas nor QuantLib;
  - the built web bundle contains no key or key-like variable;
  - the frontend type-checks and builds.
- Placeholder interface: plain pages and tables for curve, portfolio, scenarios and hedging, each showing the data date. No styling effort.
- I can run: the app locally.

### Phase 8. AI analyst and verification

- Tests:
  - tool schemas are valid and arguments are validated;
  - every numeric value in a tool result has a unique ID;
  - the `derive` tool computes correctly and rejects unknown operands;
  - a verifier case table: correct rounding passes; a last-digit error fails; $M and $B, % and bp conversions; negatives and parentheses; an untagged number fails; a context number passes; an unknown tag fails; a right number with the wrong tag fails; thousands separators; ranges;
  - a property test that correctly formatted values pass and perturbed ones fail;
  - a scripted wrong number is repaired once, and if still wrong the response is `blocked` with no prose;
  - call cap and timeout;
  - 503 retry;
  - rate limits per IP and global with a fake Redis;
  - refusal when Redis is down;
  - a live smoke test that is skipped by default.
- Placeholder chat: numbers are links that open their provenance.
- I can run: questions and a commentary draft locally.

### Phase 9. Evals

- Tests: gold functions are stable against the engine; the grader's own case table; a full dry run with the fake provider.
- Tell me the estimated cost, then run the three models with three repeats.
- I can run: one command per model and a report command.

### Phase 10. Strategy artifacts and About page

- Tests: every number in the model memo traces to an eval results file; the effort page shows "not yet recorded" while the CSV is empty.
- Stop for my timings and my review of the opportunity map.

### Phase 11. Implement the handed-off design

- I will design the interface in Claude Design and give you the handoff. Implement it without changing the API. If the design needs data the API does not provide, stop and ask.
- Every figure in the design handoff is an invented placeholder. Never copy one into the app, a fixture or a document; all displayed numbers come from the engine.
- If the handoff is not ready, tell me and go to Phase 12 with the placeholder; we will return to this phase.
- Tests: type-check, build, and a browser smoke test of each screen and each Analyst state.

### Phase 12. Production deploy and final documents

- Deploy to Vercel production after asking. Give me the steps for the firewall rule and the environment variables.
- A smoke script against the live URL: health, data date, one AI question, and a 429 once the limit is passed.
- **MODEL_CARD.md:** intended use, out-of-scope use, components, assumptions, limitations, validation evidence, the verification tolerance, and the human review procedure.
- **RESULTS.md:** generated by `scripts/make_results.py` from the QuantLib report and the eval results files, never edited by hand. It contains only measured numbers I can quote on my resume: agreement with QuantLib per measure, eval accuracy per model, and cost per question, each with its date, model ID and sample size. Add a test that runs the project's own number verifier over RESULTS.md against those source files.
- **README.md** with the live link, a two-minute tour and how to run everything.

## 14. Risks to keep in view

| Risk | What to do |
|---|---|
| A Sail model fails the probe, or capacity errors are frequent | Stop and tell me; do not switch model or tier on your own |
| Build-time Python on Vercel does not work as assumed | Stop and ask |
| A QuantLib comparison is off because of conventions | Fix the test setup so the conventions match, or report the gap; do not widen the tolerance |
| The verifier blocks too many good answers | Report the rate; improve the prompt or the tool output, not the tolerance |
| A source cannot be opened (the BNY filing, SR 26-2, Sail docs, FRED) | Stop and ask |

## 15. How to report at the end of each phase

Send me, in this order:

1. What now works, in two or three sentences.
2. The exact commands to run it and what I should see.
3. Test results: counts, and any failures with output.
4. Anything that differs from this plan and why.
5. New entries in ASSUMPTIONS.md and LIMITATIONS.md.
6. Three interview questions from this phase that I should now be able to answer.

Then wait for me to say go.

## 16. Start

Begin Phase 0. Before writing anything, tell me in a few lines what you will do in Phase 0 and what you need from me: the keys in `.env`, and a Vercel login when it is time for the skeleton deploy.

## 17. Progress log

Update this table at the end of each phase.

| Phase | Status | Date | Commit |
|---|---|---|---|
| 0. Foundations, probe, skeleton deploy | Done | 2026-11-17 | e94ac6b, 63453bf |
| 1. Yield curve | Done | 2026-11-17 | c3bbfc4 |
| 2. Bond analytics | Done | 2026-11-17 | d2bc167 |
| 3. Agency mortgage bonds | Done | 2026-11-17 | 5b9f2ec |
| 4. Portfolio | Done; awaiting go-ahead | 2026-11-17 | c786a5a, 257343a |
| 5. Scenarios | Not started | | |
| 6. Hedging | Not started | | |
| 7. Snapshot, API, placeholder interface | Not started | | |
| 8. AI analyst and verification | Not started | | |
| 9. Evals | Not started | | |
| 10. Strategy artifacts and About page | Not started | | |
| 11. Implement the handed-off design | Not started | | |
| 12. Production deploy and final documents | Not started | | |
