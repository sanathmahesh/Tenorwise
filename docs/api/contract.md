# Tenorwise API contract

For the design handoff. Generated from the code's response models by `scripts/export_contract.py`; nothing here is typed by hand.
**Field names are fixed.** If the design needs a field that is not listed, flag it instead of inventing one.
Fields marked *(added beyond PLAN.md section 8)* were approved additions to the plan's list.

## Units and signs

- Money is in US dollars, for example `market_value` and `delta_mv`. DV01 is in US dollars per 1 bp.
- Rates and yields are in percent: 4.93 means 4.93%. Shocks, shifts and spreads ending `_bp` are in basis points.
- Durations, maturities and average life are in years. Prices are per 100 of face.
- **A change is after minus before.** A negative `delta_mv`, `aoci_impact` or `htm_unrecognized` is a loss.
- DV01 and duration are positive for an ordinary long bond. A pay-fixed swap's `dv01` is negative.
- In `hedges.grid`:
  - `loss_avoided` is the swaps' gain or loss in that scenario;
  - `carry_given_up` is positive when the hedge costs carry and negative when it adds carry. Negative values occur in the real data.
- In `evidence.json`:
  - `accuracy`, `block_rate` (after the repair attempt) and `verified_but_wrong_rate` are fractions from 0 to 1;
  - latencies are in milliseconds;
  - `cost_per_question_usd` is in US dollars;
  - `runs` is the number of repeats.
- Dates are ISO strings (YYYY-MM-DD).

## Where the data comes from

- **Static files.** `GET /data/v1/<file>.json` serves the files below. They are built once per deploy, so the page loads them directly.
- **Custom scenarios.** `POST /api/scenario` computes one on demand. There is no interpolation; the engine prices it.
- **The analyst.** `POST /api/agent/ask` and `POST /api/agent/commentary`.
- **Health.** `GET /api/health`.

## IDs and list sizes (from the pinned snapshot)

- **Scenario IDs (in order):** `base` (Base (no shock)), `parallel_up_100` (+100 bp parallel), `parallel_down_100` (-100 bp parallel), `parallel_up_200` (+200 bp parallel), `parallel_down_200` (-200 bp parallel), `bear_steepener` (Bear steepener), `bull_flattener` (Bull flattener), `replay_2022` (2022 replay)
- **Hedge strategy IDs:** `unhedged` (Unhedged), `dv01_50` (50% DV01 hedge), `dv01_full` (Full DV01 hedge), `key_rate` (Key-rate-matched hedge)
- **Sector IDs:** `treasuries` (Treasuries), `agency_mbs` (Agency mortgage bonds), `agency_debt` (Agency debt), `ig_corporates` (IG corporates (proxy))
- **Accounting class IDs:** `AFS` (Available-for-sale), `HTM` (Held-to-maturity)
- **Method IDs (methods.json):** `amortized_cost`, `aoci_impact`, `aoci_net`, `avg_life`, `bond_price`, `carry_12m`, `carry_given_up`, `discount_factor`, `dv01`, `eff_convexity`, `eff_duration`, `hedge_sizing`, `htm_unrecognized`, `key_rate_dv01`, `mbs_cash_flows`, `mbs_price`, `mod_duration`, `mortgage_spread`, `par_yield`, `portfolio_aggregate`, `rate_shock`, `replay_2022`, `scenario_change`, `swap_par_rate`, `swap_value`, `unrealized`, `zero_rate`
- **Sizes:** curve points: 11 (tenors in years: 0.08333, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30); positions: 38; scenarios: 8; hedge strategies: 4; hedge grid rows: 32 (every strategy x every scenario); mortgage profile rows: 13 (shift_bp from -300 to 300); s_curve rows: 29

Scenario `base` is today's curve with no shock. The other seven are the presets.

## Static files

### meta.json

- `data_date`: string
- `build_time`: string
- `git_sha`: string or null
- `fred_series`: list of objects:
  - `id`: string
  - `title`: string
  - `use`: string
  - `observation_dates`: list of string
- `llm_model`: string or null
- `assumptions`: list of objects:
  - `id`: string
  - `text`: string
  - `where`: string
  - `effect`: string
  - `phase`: integer

### curve.json

- `data_date`: string
- `points`: list of objects:
  - `tenor_years`: number
  - `par_yield`: number (percent, semiannual bond-equivalent)
  - `zero_rate`: number (percent, continuously compounded)
  - `discount_factor`: number

### portfolio.json

- `data_date`: string
- `summary`: object:
  - `market_value`: number
  - `amortized_cost`: number
  - `unrealized`: number
  - `eff_duration`: number
  - `convexity`: number (effective (curve-based) convexity)
  - `dv01`: number
  - `key_rate_dv01`: object:
    - `2`: number
    - `5`: number
    - `10`: number
    - `30`: number
- `by_sector`: list of objects:
  - `market_value`: number
  - `amortized_cost`: number
  - `unrealized`: number
  - `eff_duration`: number
  - `convexity`: number (effective (curve-based) convexity)
  - `dv01`: number
  - `key_rate_dv01`: object:
    - `2`: number
    - `5`: number
    - `10`: number
    - `30`: number
  - `id`: string (sector or class identifier) *(added beyond PLAN.md section 8)*
  - `name`: string (display name) *(added beyond PLAN.md section 8)*
  - `weight`: number (percent of total amortized cost)
  - `market_value_by_class`: object: (market value of the sector's AFS and HTM positions (US dollars)) *(added beyond PLAN.md section 8)*
    - `AFS`: number
    - `HTM`: number
- `by_class`: list of objects:
  - `market_value`: number
  - `amortized_cost`: number
  - `unrealized`: number
  - `eff_duration`: number
  - `convexity`: number (effective (curve-based) convexity)
  - `dv01`: number
  - `key_rate_dv01`: object:
    - `2`: number
    - `5`: number
    - `10`: number
    - `30`: number
  - `id`: string (sector or class identifier) *(added beyond PLAN.md section 8)*
  - `name`: string (display name) *(added beyond PLAN.md section 8)*
  - `weight`: number (percent of total amortized cost)
- `positions`: list of objects:
  - `id`: string
  - `name`: string
  - `sector`: string
  - `class`: "AFS" | "HTM"
  - `face`: number
  - `coupon`: number (percent; for mortgage pools, the net coupon)
  - `maturity_years`: number
  - `book_yield`: number (percent)
  - `price`: number (per 100 of face)
  - `market_value`: number
  - `amortized_cost`: number
  - `unrealized`: number
  - `eff_duration`: number
  - `mod_duration`: number (yield-based)
  - `convexity`: number (effective (curve-based))
  - `dv01`: number
  - `key_rate_dv01`: object:
    - `2`: number
    - `5`: number
    - `10`: number
    - `30`: number
  - `stylized`: boolean (true for stylized agency mortgage pools) *(added beyond PLAN.md section 8)*
  - `proxy_for`: string or null (BNY line an IG-corporate proxy stands in for) *(added beyond PLAN.md section 8)*
- `source`: object:
  - `text`: string
  - `url`: string

### mbs.json

- `data_date`: string
- `stylized`: boolean
- `stylized_note`: string
- `pool`: object:
  - `wac`: number
  - `net_coupon`: number
  - `age_months`: integer
  - `remaining_months`: integer
  - `discount_spread_bp`: number
- `mortgage_rate`: object:
  - `date`: string
  - `mortgage_rate`: number
  - `ten_year_yield`: number
  - `spread`: number
  - `series`: string
  - `attribution`: string
- `prepayment_model`: object:
  - `cpr_min`: number
  - `cpr_max`: number
  - `k`: number
  - `x0`: number
  - `ramp_months`: integer
- `comparison_treasury_bond`: object:
  - `coupon`: number
  - `maturity_years`: number
- `profile`: list of objects:
  - `shift_bp`: number
  - `price`: number
  - `eff_duration`: number
  - `avg_life_years`: number
  - `cpr`: number (percent, first projected month)
  - `eff_convexity`: number *(added beyond PLAN.md section 8)*
  - `incentive_pct`: number (refinancing incentive in percentage points, pool WAC minus the mortgage rate after the shift) *(added beyond PLAN.md section 8)*
- `comparison_treasury`: list of objects:
  - `shift_bp`: number
  - `price`: number
- `s_curve`: list of objects:
  - `incentive_pct`: number
  - `cpr`: number (percent, seasoned)

### scenarios.json

- `data_date`: string
- `base_market_value`: number *(added beyond PLAN.md section 8)*
- `scenarios`: list of objects:
  - `id`: string
  - `name`: string
  - `description`: string
  - `shock_bp_by_tenor`: list of objects:
    - `tenor_years`: number
    - `shock_bp`: number
  - `total`: object:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
  - `by_sector`: list of objects:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
    - `id`: string
    - `name`: string
  - `by_class`: list of objects:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
    - `id`: string
    - `name`: string
  - `shocked_curve`: list of objects:
    - `tenor_years`: number
    - `par_yield`: number (percent, semiannual bond-equivalent)
    - `zero_rate`: number (percent, continuously compounded)
    - `discount_factor`: number
  - `floor_bound`: boolean (shocked par yields hit the 0% floor) *(added beyond PLAN.md section 8)*
  - `floored_tenor_years`: list of number *(added beyond PLAN.md section 8)*

### hedges.json

- `data_date`: string
- `swap_spread_bp`: number (swap curve = Treasury zero curve + this spread) *(added beyond PLAN.md section 8)*
- `hedged_book`: "AFS" *(added beyond PLAN.md section 8)*
- `afs_dv01`: number *(added beyond PLAN.md section 8)*
- `strategies`: list of objects:
  - `id`: string
  - `name`: string
  - `swaps`: list of objects:
    - `tenor_years`: number
    - `notional`: number
    - `fixed_rate`: number (percent)
    - `dv01`: number (US dollars per bp; negative for pay-fixed)
  - `key_rate_dv01_after`: object:
    - `2`: number
    - `5`: number
    - `10`: number
    - `30`: number
  - `dv01_after`: number (AFS + swaps) *(added beyond PLAN.md section 8)*
- `grid`: list of objects:
  - `strategy_id`: string
  - `scenario_id`: string
  - `securities_delta_mv`: number
  - `swap_pnl`: number
  - `net_delta_mv`: number
  - `aoci_net`: number
  - `loss_avoided`: number
  - `carry_given_up`: number
  - `net_carry`: number

### methods.json

- `data_date`: string
- `methods`: map from method ID to object:
  - `name`: string
  - `plain_english`: string
  - `formula`: string
  - `notes_anchor`: string

### evidence.json

- `data_date`: string
- `models`: list of objects:
  - `id`: string
  - `accuracy`: number
  - `block_rate`: number
  - `verified_but_wrong_rate`: number
  - `latency_p50_ms`: number
  - `latency_p95_ms`: number
  - `cost_per_question_usd`: number
  - `runs`: integer
- `questions`: list of objects:
  - `id`: string
  - `category`: string
  - `text`: string
  - `results`: map from model ID to "pass" | "fail" | "blocked"
- `quantlib`: list of objects:
  - `measure`: string
  - `instruments`: integer
  - `max_abs_diff`: number
  - `unit`: string
- `quantlib_report_generated_at`: string *(added beyond PLAN.md section 8)*

## Endpoints

### GET /api/health

- `status`: "ok" | "no_snapshot"
- `data_date`: string or null
- `build_time`: string or null
- `git_sha`: string or null
- `model_id`: string or null

### POST /api/scenario

Request: exactly one of a parallel shift or key-rate shocks. Each is limited to -300 to +300 bp.

- `parallel_bp`: number or null
- `key_rate_bp`: object or null:
  - `2`: number
  - `5`: number
  - `10`: number
  - `30`: number

Response: one scenario, shaped like an entry in `scenarios.json` with `id` "custom", plus its hedge grid rows.

- `data_date`: string
- `scenario`: object:
  - `id`: string
  - `name`: string
  - `description`: string
  - `shock_bp_by_tenor`: list of objects:
    - `tenor_years`: number
    - `shock_bp`: number
  - `total`: object:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
  - `by_sector`: list of objects:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
    - `id`: string
    - `name`: string
  - `by_class`: list of objects:
    - `delta_mv`: number
    - `delta_mv_pct`: number (percent of base market value)
    - `aoci_impact`: number
    - `htm_unrecognized`: number
    - `carry_12m`: number
    - `id`: string
    - `name`: string
  - `shocked_curve`: list of objects:
    - `tenor_years`: number
    - `par_yield`: number (percent, semiannual bond-equivalent)
    - `zero_rate`: number (percent, continuously compounded)
    - `discount_factor`: number
  - `floor_bound`: boolean (shocked par yields hit the 0% floor) *(added beyond PLAN.md section 8)*
  - `floored_tenor_years`: list of number *(added beyond PLAN.md section 8)*
- `grid`: list of objects:
  - `strategy_id`: string
  - `scenario_id`: string
  - `securities_delta_mv`: number
  - `swap_pnl`: number
  - `net_delta_mv`: number
  - `aoci_net`: number
  - `loss_avoided`: number
  - `carry_given_up`: number
  - `net_carry`: number

### POST /api/agent/ask and POST /api/agent/commentary

Ask request (commentary takes an empty object `{}`):

- `question`: string
- `history`: list of objects:
  - `role`: "user" | "assistant"
  - `content`: string

Response:

- `status`: "answered" | "cannot_answer" | "blocked" | "error"
- `answer_md`: string
- `sections`: list of objects:
  - `heading`: string
  - `body_md`: string
- `values`: map from value tag (v1, v2, ...) to object:
  - `value`: number
  - `unit`: string
  - `display`: string
  - `label`: string
  - `tool`: string
  - `args`: object (free-form)
  - `method`: string
  - `inputs`: list of string
- `checks`: list of objects:
  - `token`: string
  - `tag`: string or null
  - `passed`: boolean
  - `reason`: string
- `trace`: list of objects:
  - `tool`: string
  - `args`: object (free-form)
  - `ms`: integer
- `usage`: object:
  - `model`: string
  - `served_tier`: string or null
  - `llm_calls`: integer
  - `prompt_tokens`: integer
  - `completion_tokens`: integer
  - `cost_usd`: number or null
  - `latency_ms`: integer
  - `cost_is_upper_bound`: boolean (cached tokens were not reported) *(added beyond PLAN.md section 8)*
- `fallback`: list of objects or null:
  - `tool`: string
  - `label`: string
  - `display`: string
- `data_date`: string or null
- `notice`: string or null ('Draft, requires human review' on commentary) *(added beyond PLAN.md section 8)*
- `error`: string or null (why status is error) *(added beyond PLAN.md section 8)*
- `request_id`: string or null *(added beyond PLAN.md section 8)*
- `verification_rule`: string (the stated tolerance, for display) *(added beyond PLAN.md section 8)*

How the analyst's response is shown:

- **Number tags.** In `answer_md` and in each `sections[].body_md`, every number is followed by a tag such as `[[v12]]`. The interface hides the tag and makes the number a link that opens `values.v12`: its label, the tool and arguments, the method, and its inputs for derived figures.
- **`answered`:** show `answer_md` for a question, or `sections` for commentary, with `verification_rule` nearby.
- **`cannot_answer`:** show `answer_md`, which explains why the question can't be answered.
- **`blocked`:** no prose. Show `fallback`, a table of raw engine results, and say verification failed. `answer_md` and `sections` are empty.
- **`error`:** show `error`.
- **Commentary:** always show `notice` ("Draft, requires human review").
- **HTTP errors** return `{"detail": "..."}` instead of a response body:
  - 429: daily limit reached (per IP address, or global);
  - 503: AI temporarily unavailable;
  - 422: invalid input, for example an empty question or one over 1,000 characters.
- **Not shown in the interface:** `checks`, `trace` and `usage`. They are available for a details drawer if wanted.

## Required on screen

- The market data date: `meta.data_date`.
- "Stylized" on the agency mortgage pool, its charts and mortgage positions: `mbs.stylized`, `mbs.stylized_note` and `positions[].stylized`.
- "Proxy" on IG corporates: `positions[].proxy_for` and the sector name.
- The portfolio source citation: `portfolio.source.text` and `portfolio.source.url`.
- The mortgage rate attribution: `mbs.mortgage_rate.attribution`.
- The FRED footer: "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis. By using Tenorwise you agree to the FRED® API Terms of Use", with a link to https://fred.stlouisfed.org/docs/api/terms_of_use.html.
- Assumptions: `meta.assumptions`, wherever a result depends on one. For example, the swap spread (`hedges.swap_spread_bp`) is an assumption.

## Pages rendered from Markdown at build time

The About page bodies are the repository's `docs/strategy/*.md` files: the opportunity map, effort, model memo, risks and controls, rollout plan and decision log.
- **Styling:** design the styles for generic Markdown: headings, paragraphs, lists, bold, code spans, links and wide tables (which need to scroll on phone).
- **Effort timings:** come from a CSV. Until it has rows, show "Timings not yet recorded".
