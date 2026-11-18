# Notes

One section per phase. Each covers the finance concepts in plain English, how
the code implements them, why this design and what was rejected, what would
break it, and interview questions with short model answers.

## Sign conventions

Stated once here and used everywhere in the code, the API and the interface.

- **Rates** are decimals inside the engine (0.05 means 5%). The API and the
  interface show them in percent.
- **Basis points** measure shocks and changes in rates: 1 bp = 0.01
  percentage point = 0.0001 as a decimal.
- **A positive shock means yields go up.** A shock of +100 bp turns a 5.00%
  par yield into 6.00%.
- **A change is "after minus before"**: the value on the shocked curve minus
  the value on the base curve. So a negative change in a bond's value is a
  loss.
- **Duration and DV01 are positive for an ordinary long bond.** They measure
  how much value is *lost* when rates rise: DV01 = (value at −1 bp − value at
  +1 bp) / 2, in dollars per basis point. A negative key-rate duration means
  that bucket's bump *raises* the value.
- **Convexity is positive when gains from falling rates exceed losses from
  rising rates of the same size.** Ordinary bonds have positive convexity;
  mortgage bonds (Phase 3) can have negative convexity.
- **Prices** are dirty (including accrued interest) unless labelled clean, in
  the same units as face (100 = per 100 face).

---

## Phase 0. Foundations, provider probe, skeleton deploy

### What the project is about, in plain English

A bank holds a large portfolio of bonds. A bond pays fixed amounts of interest
and then returns its principal. When market interest rates rise, newly issued
bonds pay more, so an existing bond paying the old, lower rate becomes worth
less. The bank's portfolio therefore loses value when rates rise. Tenorwise
measures how much it would lose under different rate moves, and compares ways
of offsetting (hedging) that loss against what each hedge costs. Each concept
gets its full explanation in the phase that builds it: the yield curve in
Phase 1, duration and DV01 in Phase 2, mortgage bonds in Phase 3, accounting
classes (AFS and HTM) in Phase 4, scenarios in Phase 5 and swaps in Phase 6.

Phase 0 builds no finance. It sets up the plumbing everything else depends on.

### How the code implements it

- **Static snapshot.** [scripts/build_snapshot.py](scripts/build_snapshot.py) calls
  [tenorwise/snapshot/build.py](tenorwise/snapshot/build.py), which writes the same
  JSON bytes into two folders: `web/public/data/v1/` (served as static files)
  and `data/snapshot/v1/` (read by the API function). For now it writes only
  `meta.json` (the contract fields, with no market data yet) and
  `build_check.json` (proof that numpy and scipy ran at build time).
- **API.** [tenorwise/api/app.py](tenorwise/api/app.py) defines the FastAPI app with
  `/api/health` and a temporary `/api/deploy-check`.
  [api/index.py](api/index.py) is the Vercel entrypoint that exposes `app`.
  [tenorwise/snapshot/store.py](tenorwise/snapshot/store.py) reads snapshot files on
  every request and never writes.
- **Vercel build.** [vercel.json](vercel.json) pins the framework to Vite, runs
  [scripts/vercel_build.sh](scripts/vercel_build.sh) (Python snapshot first, then
  the Vite build), and rewrites `/api/*` to the function.
- **Provider probe.** [scripts/probe_llm.py](scripts/probe_llm.py) tests each
  candidate model on Sail and writes [docs/provider-probe.md](docs/provider-probe.md)
  plus the full response bodies in `docs/provider-probe-raw.json`.
- **Placeholder page.** [web/src/App.tsx](web/src/App.tsx) shows the static files
  and the two function responses side by side, with the market data date at
  the top.

### What the provider probe found (run 2026-11-18 01:21 UTC, one run)

- All three candidate models (`zai-org/GLM-5.3`,
  `deepseek-ai/DeepSeek-V4.1-Flash-1017`, `moonshotai/Kimi-K3.1-Pro`) passed
  every test: plain completion, a function-tool round trip, `tool_choice`
  "required" with `service_tier` "asap" set explicitly, and a `json_schema`
  reply. Every response reported `service_tier: "asap"`. So ordinary function
  tools do run on the asap tier, which no Sail docs page states directly.
- Usage on every response included `prompt_tokens`, `completion_tokens` and
  `total_tokens`. It also included two fields Sail does not document:
  `prompt_tokens_details.cached_tokens` and
  `completion_tokens_details.reasoning_tokens`. Cached tokens are therefore
  reported, and costs can price cached input at the cached rate.
- `GET /v1/models` returned more than IDs. Each entry also had
  `input_modalities` and `pricing_usd_per_million_tokens` per tier. PLAN.md
  section 4 says IDs only, and Sail's OpenAPI schema lists only `id`, `object`,
  `created` and `owned_by`.
- GLM-5.3 with `reasoning_effort: "none"` returned HTTP 400
  `unsupported_reasoning_effort`, as documented.
- The probe cost $0.0085 in total. That is computed from the usage each
  response reported at Sail's asap list prices, not read from an invoice.
- Latency, measured from the developer's machine on 15 successful calls,
  clustered tightly near 1.1 s, 3.1 s and 5.1 s. Something on the provider
  side may work in steps of about 2 seconds. Too few calls to conclude
  anything; watch for it in the Phase 9 latency figures.

### What the skeleton deploy proved (2026-11-18 01:54 UTC, deployment `dpl_D7D7FRMob4ikiwNsMjGHpCAThwuu`)

PLAN.md section 4 listed two things as unconfirmed. Both are now confirmed.

- **A Python script can run in the build step of a Vite-plus-`/api` project.**
  Vercel's build image had Python 3.12.15 and uv 0.13.5 on the PATH. The
  snapshot script ran with numpy and scipy installed from `uv.lock` with
  `--no-dev`.
- **Files the build step writes are bundled into the function.** The build
  log shows Vercel builds the Python function *after* the build command
  ("Installing required dependencies from uv.lock" comes after the Vite
  build). The live `/api/deploy-check` returned `build_check.json` as read
  inside the function, and it equals the static copy served at
  `/data/v1/build_check.json`.
- **numpy 2.5.5 and scipy 1.18.1 work in the function**, on Python 3.12.16.
  The runtime patch version differs from the build image's 3.12.15.
- **pandas and QuantLib are not installed in the function** (`importable`
  reports false for both).
- `/api/*` rewrites reach FastAPI with the full path intact (`/api/health`
  answered from the `@app.get("/api/health")` route).
- Vercel assigned the project's first deployment to production
  (`tenorwise.vercel.app`, publicly reachable), not to a preview. See D-012.

### Why this design, and what was rejected

See [docs/strategy/decision-log.md](docs/strategy/decision-log.md), D-001 to
D-013. The ones most likely to come up in an interview:

- **Compute at build time, serve static JSON.** Market data changes once a
  day, so the standard scenarios can be computed once per deploy. The function
  then only does work that depends on user input (custom scenarios, agent tool
  calls). That makes the site cheap, fast and hard to break.
- **The function holds nothing in memory and writes nothing.** Serverless
  instances are created and discarded at will, so any in-memory state would
  be unreliable. The snapshot is read from files on each request.
- **pandas and QuantLib are not installed in production at all.** That is a
  stronger guarantee than "not imported".
- **Probe the provider before building on it.** The agent design depends on
  function tools working on the low-latency tier, and the docs did not say so
  directly. One cheap script turned that uncertainty into a recorded fact.

### What would break it

- Vercel changing how file-based `/api` functions are built or bundled. Its
  docs now present the layout as support for "existing projects", and the
  fallback is Services (beta). See D-001.
- The build image lacking `uv` or Python 3.12. The build script falls back to
  installing uv with pip; if Python itself is missing, the build fails loudly.
- Sail retiring a candidate model at short notice. The model ID is
  configuration (`LLM_MODEL`), and the changelog showed a one-week notice on
  2026-11-12.
- A future change that adds a module-level cache or a runtime file write.
  Ground rule 7 forbids both, and code review has to catch them.

### Interview questions

1. **Why precompute at build time instead of computing on request?**
   The inputs (end-of-day Treasury yields) change once a day, and the standard
   outputs are the same for every visitor. Precomputing makes most pages
   static files, keeps the function small, and means a provider or FRED outage
   cannot break the pages that are already built.
2. **How do you know QuantLib isn't in production?**
   It is in the dev dependency group, which the deployed function never
   installs. A test imports the deployed app in a fresh interpreter and fails
   if pandas or QuantLib is loaded. The Phase 0 deploy check reports whether
   each is installed in the live function.
3. **How are API keys kept out of the browser and the repo?**
   Keys live only in environment variables. `.env` is in `.gitignore` and
   `.vercelignore`. The frontend reads no environment variables at all (Vite
   exposes only `VITE_`-prefixed ones and there are none). A test checks that
   the health response never contains a key.
4. **Why test the LLM provider before writing the agent?**
   The design relies on function calling for every structured output,
   including the final answer, and on the low-latency tier. The probe confirmed
   both for all three candidates and recorded usage fields the cost reporting
   will rely on.
5. **What happens if Sail retires the model you use?**
   The model ID is an environment variable, so switching is a configuration
   change plus a re-run of the probe and evals. Nothing outside the provider
   module knows it is talking to Sail.
6. **Why retry only some provider errors?**
   429 and the 503 capacity errors are refused before the model runs, so a
   retry cannot double-charge. A timeout might mean the request is still
   running, so a blind retry could pay twice.
7. **How did you prove the serverless function can read what the build produced?**
   The build writes the same JSON file in two places: one served as a static
   file, one inside the function's folder. A temporary endpoint reads its copy
   from inside the deployed function and returns it, and the two copies
   matched. The build log also showed the function being packaged after the
   build step ran.

---

## Phase 1. Yield curve

### Finance concepts, in plain English

- **Basis point (bp).** One hundredth of a percentage point. Rate moves are
  quoted in basis points: "+25 bp" turns 4.00% into 4.25%.
- **Treasury par yield.** The US government borrows by selling bonds. A *par
  yield* is the coupon rate at which a new bond of a given maturity would sell
  for exactly its face value (100). FRED publishes these daily for 11
  maturities, from 1 month to 30 years (series DGS1MO ... DGS30, from the
  Federal Reserve's H.15 release). The 16 November 2026 values run from 4.10%
  at 1 month to 5.51% at 20 years.
- **Yield curve.** Those yields plotted against maturity. On 16 November 2026
  the curve slopes upward to 20 years and dips slightly at 30 years.
- **Compounding.** The same interest rate can be quoted different ways.
  *Semiannual* (how US Treasury yields are quoted) pays half the annual rate
  every six months. *Simple interest* pays the rate once, pro rata, at the
  end. *Continuous compounding* is the limit of compounding ever more often.
  It makes the maths clean: a dollar due at time t is worth exp(-z·t) today.
- **Discount factor.** What one dollar paid at a future date is worth today.
  At 10 years on this curve it is about 0.60.
- **Zero rate.** The single interest rate, for one date, that turns a future
  dollar into today's value: DF(t) = exp(-z(t)·t). Once you have zero rates
  for every date, you can value any fixed cash flow by discounting each
  payment separately.
- **Bootstrapping.** Par yields describe bonds that pay coupons along the way,
  but valuation needs zero rates. Bootstrapping recovers them one maturity at
  a time, shortest first. Each par bond's early coupons are discounted with
  zero rates already found, which leaves one unknown, the zero rate at its
  maturity. That unknown is solved so the bond prices at exactly 100.
- **Interpolation.** There are only 11 points; a bond paying in 8.5 years
  needs a rate in between. Tenorwise draws a straight line between
  neighbouring zero rates, and holds the end values flat beyond 1 month and
  30 years.
- **Rate shock.** A hypothetical rate move. A *parallel* shock moves every
  maturity by the same amount. A *key-rate* shock moves one region of the
  curve, shaped like a tent centred on 2, 5, 10 or 30 years. Because the four
  tents add up to 1 at every maturity, bumping all four by 1 bp is the same
  as a 1 bp parallel shift. That property is what lets the key-rate risks
  in Phase 2 add up to the total.

### How the code implements it

- [tenorwise/curve/fred.py](tenorwise/curve/fred.py): fetches the 11 series and
  parses FRED's "." (missing) into `None`. It picks the most recent date on
  which all 11 have a value, without filling forward, and refuses data more
  than 7 days older than the build date. Error messages are written locally
  and scrubbed of the API key.
- [tenorwise/curve/bootstrap.py](tenorwise/curve/bootstrap.py): `ParCurve`,
  `ZeroCurve` and `bootstrap()`. Tenors of 6 months and under use
  `z = ln(1 + y·T)/T`; longer tenors solve the par-bond equation with
  `scipy.optimize.brentq`. Interpolation is `numpy.interp`, which is linear
  between points and flat beyond the ends, exactly the rule.
- [tenorwise/curve/shocks.py](tenorwise/curve/shocks.py): every shock is an
  11-element vector of basis points added to the par yields. The curve is then
  rebuilt with the same `bootstrap()`, and yields are floored at 0% with a
  flag. Each tent is `numpy.interp` of a one-hot vector over the nodes
  2, 5, 10 and 30, which is why the four sum to exactly 1.
- [tenorwise/curve/fixture.py](tenorwise/curve/fixture.py) and
  [data/fixtures/fred_treasury_par_2026-11-17.json](data/fixtures/fred_treasury_par_2026-11-17.json):
  the pinned FRED responses, stored verbatim, used by tests and later evals.
  The fetch date stands in for the build date, so the fixture never goes
  stale. [scripts/update_fred_fixture.py](scripts/update_fred_fixture.py)
  makes a new one.
- `uv run python -m tenorwise.curve` ([tenorwise/curve/__main__.py](tenorwise/curve/__main__.py))
  prints the curve, its data date and the FRED notice, with optional shocks.
- [tests/benchmark/quantlib_curve.py](tests/benchmark/quantlib_curve.py): the
  same bootstrap in QuantLib, with conventions that reduce to ours.

### Results on the pinned data (data date 2026-11-16)

These figures were measured by running the code, not estimated:

- The 11 input instruments reprice to 100 within 1.3e-13 (the test requires 1e-8).
- Zero rates agree with QuantLib's piecewise linear-zero curve within 1.5e-13
  as a decimal rate, about 0.0000000015 bp, at worst at 3 months. The
  tolerance, fixed before the first run, is 1e-10.
- Real FRED data contains "." on bond-market holidays: 12 October and
  11 November 2026 in the fixture window.

### Why this design, and what was rejected

- **Linear interpolation in zero rates**, as the plan specifies. Splines or
  monotone-convex methods give smoother forward rates, which matters for
  pricing products that depend on forwards between curve points. They are
  harder to explain and to test exactly, and nothing in Tenorwise prices such
  products.
- **One shock mechanism for everything.** Scenarios, duration bumps and
  key-rate bumps all go through `apply_shock()`, so they cannot disagree about
  what "rates up 1 bp" means.
- **Fail the build on stale or incomplete data** instead of filling forward.
  A curve mixing two dates would show a market that never existed. The site
  keeps serving the previous deployment.
- **Fixture holds raw responses, not a cleaned table.** Tests then exercise
  the same parsing code as production, including the "." handling.

### An inconsistency in the plan, flagged for decision

The plan prices tenors of 6 months and under as one simple-interest payment,
DF = 1/(1 + y·T), and longer ones as semiannual bonds. On a flat par curve the
two conventions give different zero rates. At a flat 4%, the 1-month and
3-month zero rates come out 3.3 bp and 2.0 bp above the 3.96% level that holds
from 6 months on. These figures are calculated from the formulas,
12·ln(1 + 0.04/12) and 4·ln(1.01) against 2·ln(1.02). So the plan's test "a
flat par curve gives a flat zero curve" cannot pass at 1 and 3 months as
written. The test was split: flat from 6 months out, and the short end
checked against its own simple-interest formula. The alternative would treat
the short end as semiannual too, DF = (1 + y/2)^(-2T). That would make the
curve flat, but it changes the plan, so the owner decides. Decision log D-021.

### What would break it

- FRED changing its response format or the "." convention. The parser fails
  loudly on any other non-numeric value.
- A day when one series is missing for more than 7 days. The build then fails
  instead of using a mixed or stale curve.
- Very low or negative rates. The 0% floor binds and the result is flagged,
  but the model cannot represent negative yields.
- Key-rate shocks are applied to par yields, not zero rates. A bump in one
  region moves zero rates elsewhere through the bootstrap. On the pinned curve,
  +25 bp on the 10-year tent leaves the 30-year par yield unchanged but lowers
  the 30-year zero rate by 13.6 bp. The 30-year bond's coupons from 10 to 20
  years are now discounted more heavily, so its later cash flows must be
  discounted less for it to still price at 100.

### Interview questions

1. **What is a zero rate, and why not just use the par yields?**
   A par yield blends the rates for every coupon date of one bond. A zero
   rate applies to a single date. To value a portfolio of different bonds,
   you discount each cash flow at the rate for its own date, so you need
   zero rates. Bootstrapping extracts them from the par yields.
2. **Walk me through the bootstrap.**
   Short tenors are single payments, so their discount factor comes straight
   from the yield. For each longer tenor, the par bond's early coupons are
   discounted with zero rates already found. The only unknown is the zero
   rate at its maturity, solved so the bond prices at 100. Then move to the
   next tenor.
3. **How do you know the curve is right?**
   The 11 input bonds reprice to 100 within 1.3e-13. An independent QuantLib
   build with matching conventions agrees within 1.5e-13 in rate. Unit tests
   also cover flat curves, interpolation, and positive, falling discount
   factors.
4. **A 10-year shock lowered the 30-year zero rate. Is that a bug?**
   No. Shocks move par yields. The 30-year bond's coupons in the bumped
   region are worth less, so with its own par yield unchanged, its later cash
   flows must be discounted less for it still to price at par. It is a
   property of bootstrapping from par yields, and it is listed in
   LIMITATIONS.md.
5. **Why must the key-rate tents add up to 1?**
   So that bumping every bucket by 1 bp is exactly a 1 bp parallel shift.
   The key-rate risks then add up to total rate risk, and nothing is lost
   or counted twice.
6. **Why fail the build on stale data rather than use yesterday's numbers?**
   A model that silently runs on old data gives confident wrong answers.
   Failing keeps the last good deployment live, and the date on screen stays
   true.
7. **What does linear interpolation in zero rates cost you?**
   The implied forward rates jump at every curve point. It is fine for
   valuing fixed cash flows, but would be poor for pricing anything that
   depends on forward rates between points.

---

## Phase 2. Bond analytics

### Finance concepts, in plain English

- **Fixed-rate bond.** A loan you can buy and sell. It pays a fixed coupon
  (half the annual rate every six months) and returns its face value at
  maturity. Tenorwise's bonds have no call features and no floating rates.
- **Dirty price, clean price, accrued interest.** If you buy a bond between
  coupon dates, the seller has earned part of the next coupon. *Accrued
  interest* is that part: the semiannual coupon times the fraction of the
  half-year already elapsed. The *dirty* price is what you actually pay,
  which is the present value of all future payments. The *clean* price is
  the dirty price minus accrued; markets quote clean prices so they don't
  jump on coupon dates.
- **Spread.** Extra yield investors demand to hold a bond that is riskier
  or less liquid than a Treasury. Tenorwise adds a constant spread for each
  sector to the Treasury zero rates.
- **Yield (yield to maturity).** The single rate that, applied to every cash
  flow, reproduces the bond's price. It is a summary of the price, not a
  rate the bond actually earns on each cash flow.
- **Duration.** How sensitive the price is to rates, measured in years.
  *Macaulay duration* is the present-value-weighted average time to the
  bond's cash flows. *Modified duration* is approximately the percentage
  price drop for a 1 percentage point rise in the bond's own yield.
  *Effective duration* measures the same thing by actually shifting the
  yield curve and repricing, which is the version that also works for
  mortgage bonds and swaps.
- **Convexity.** Duration itself changes as rates move. Positive convexity
  means the price curve bends upward: you gain more when rates fall than you
  lose when they rise by the same amount. Duration alone misses this, so
  duration plus convexity gives a much better estimate for large moves.
- **DV01 ("dollar value of a basis point").** The dollars lost when rates
  rise 1 bp. A bank's risk desk adds DV01s across positions to get the
  portfolio's total rate exposure in dollars.
- **Key-rate DV01 and key-rate duration.** The DV01 broken down by where on
  the curve the rate move happens (around 2, 5, 10 or 30 years). A 2-year
  bond's risk sits almost entirely in the 2-year bucket; a 30-year bond's in
  the 30-year bucket. Hedges in Phase 6 use this breakdown to match each
  bucket.

### How the code implements it

- [tenorwise/instruments/bond.py](tenorwise/instruments/bond.py): `FixedRateBond`
  (coupon, whole months to maturity, face). Cash flows run at T, T−6
  months, ... while positive, so an off-cycle bond (e.g. 123 months) has a
  short time to its next coupon and non-zero accrued. `dirty_price(curve,
  spread)` discounts each cash flow at `exp(-(z(t) + s)·t)`.
- [tenorwise/analytics/yield_measures.py](tenorwise/analytics/yield_measures.py):
  yield, Macaulay and modified duration and convexity for any stream of
  fixed cash flows. The yield is compounded semiannually and solved with
  `brentq`. The bond delegates to these functions, and Phase 3's mortgage
  cash flows can reuse them.
- [tenorwise/analytics/risk.py](tenorwise/analytics/risk.py): curve-based risk.
  `build_risk_curves()` builds the 12 bumped curves once per base curve:
  ±25 bp and ±1 bp parallel, and ±1 bp on each of the four tents.
  `risk_measures(price_fn, curves)` reprices any instrument on them. The
  instrument only supplies a function from curve to value, which is why
  mortgage pools and swaps can plug in later.
- `uv run python -m tenorwise.analytics --coupon 4.5 --maturity-months 123`
  ([tenorwise/analytics/__main__.py](tenorwise/analytics/__main__.py)) prints
  price, yield, both kinds of duration, convexity, DV01 and key-rate DV01s.
- [tests/benchmark/quantlib_bonds.py](tests/benchmark/quantlib_bonds.py) and
  [scripts/quantlib_report.py](scripts/quantlib_report.py): QuantLib prices
  the same 170 bonds on Tenorwise's zero curve, with conventions that reduce
  to ours. The measured differences go to
  [docs/evidence/quantlib_report.json](docs/evidence/quantlib_report.json).

### Results on the pinned data (data date 2026-11-16)

These figures were measured by running the code:

- **QuantLib agreement across 170 bonds.** The grid has coupons from 0% to
  8%, maturities from 6 months to 30 years including off-cycle ones, and
  spreads of 0 and 1%. Maximum absolute differences:
  - dirty price 1.4e-13 and clean price 1.6e-13, per 100 face;
  - yield 7.1e-16;
  - Macaulay and modified duration 5.0e-14 years;
  - convexity 2.0e-12.
- **Key-rate durations add up.** The four key-rate durations sum to the
  effective duration within 0.096% at worst (30-year zero-coupon bond);
  the plan allows 0.5%.
- **Convexity matters at 100 bp.** For ±100 bp, duration plus convexity
  predicts the actual reprice within 1.54% of the change at worst (30-year
  zero, +100 bp). Duration alone misses by up to 15.9%.
- **Example: a 4.5% bond with 10y 3m to maturity.** Dirty price 96.109,
  yield 5.135%, modified duration 7.963, effective duration 8.014, DV01
  $0.0770 per 100 face per bp. Its key-rate durations: −0.026 (2y),
  −0.110 (5y), 8.031 (10y), 0.118 (30y).

### Two kinds of DV01, and why they differ on a real curve

*Formula* DV01 comes from the bond's own yield: modified duration × price ×
0.0001. *Bump-and-reprice* DV01, the definition Tenorwise uses, raises all 11
par yields by 1 bp, rebuilds the curve and reprices. On a flat curve they are
the same thing. On a synthetic flat 5% curve they agree within 0.012% for
every bond in the grid; with a 1% spread they differ by exactly the
compounding factor exp(s/2), about 0.5%.

On the real 16 November curve, which slopes upward, they differ by up to
+4.45% (20-year zero-coupon bond, no spread). The reason is that the
bootstrap amplifies a parallel par-yield shift at long maturities, so a 1 bp
par move shifts a 20-year zero bond's own yield by 1.045 bp. It is the same
spillover as Phase 1's key-rate example. The owner chose (D-024) to test the
formula match on a flat curve, and to test on the real curve that the
bond's own-yield move explains the gap exactly.

Tenorwise's headline duration and DV01 are bump-and-reprice measures,
because the scenarios in Phase 5 move the curve the same way. Modified
duration is shown for reference and labelled as yield-based.

### Why this design, and what was rejected

- **One risk engine for every instrument.** Bump the curve, reprice, and
  divide. It needs no formulas specific to each instrument, which is why it
  can handle mortgage bonds whose cash flows change with rates. The
  alternative, analytic duration formulas per instrument, breaks as soon as
  cash flows depend on rates.
- **Build the 12 bumped curves once.** Each bump is a full rebuild of the
  curve, so for a 40-position portfolio this does 12 rebuilds instead of 480.
- **Central differences.** Bumping both up and down cancels the convexity
  error in duration and keeps the estimates accurate with modest bump sizes.
- **Key-rate bumps of ±1 bp** (the plan does not give a size). They match
  the DV01 bump, so key-rate DV01s are directly "dollars per bp in this
  bucket".

### What would break it

- Any bump hitting the 0% floor. `RiskCurves.floor_bound` flags it and the
  CLI prints a warning, but the measures are then distorted.
- Instruments with zero value (a swap at inception). Duration divides by
  value, so `risk_measures` returns `None` for durations and keeps DV01.
- Reading modified duration as the curve risk on a steep curve. It
  understates long-bond DV01 by up to about 4.5% on the pinned curve.

### Interview questions

1. **What's the difference between dirty and clean price?**
   Dirty is what you pay: the present value of all future cash flows. Clean
   removes the interest the seller has earned since the last coupon, so
   quoted prices don't jump on coupon dates.
2. **Modified versus effective duration?**
   Modified duration comes from the bond's own yield and assumes cash flows
   are fixed. Effective duration shifts the actual curve and reprices, so it
   works for any instrument, including ones whose cash flows change with
   rates.
3. **Why did your formula DV01 and bump DV01 disagree by 4% for a long
   bond?**
   They answer different questions. One moves the bond's own yield by 1 bp;
   the other moves the 11 par yields by 1 bp. On an upward-sloping curve,
   bootstrapping turns a 1 bp par move into a larger zero-rate move at long
   maturities. On a flat curve they agree within 0.012%.
4. **Why does a 10-year bond have negative key-rate duration at 5 years?**
   Bumping the 5-year region raises par yields up to 10 years less than at
   5. To keep the 10-year par bond at par, the bootstrapped 10-year zero
   rate falls, and the bond's principal is paid near 10 years, so its value
   rises. The four buckets still add up to total duration.
5. **How do you know your bond maths is right?**
   It agrees with QuantLib on 170 bonds to about 1e-13 in price, and unit
   tests check textbook identities. A par bond prices at 100; a zero-coupon
   bond's Macaulay duration equals its maturity; clean plus accrued equals
   dirty; price to yield to price round-trips.
6. **Why bother with convexity?**
   For a 100 bp move, duration alone missed the actual price change by up
   to 16% on the test grid; adding convexity cut the worst error to 1.5%.
7. **Why are the key-rate buckets useful for hedging?**
   A single DV01 hedge protects against parallel moves only. Matching each
   bucket also protects against changes in the curve's shape, which is the
   key-rate-matched hedge in Phase 6.

---

## Phase 3. Agency mortgage bonds (stylized)

### Finance concepts, in plain English

- **Agency mortgage pass-through.** A bond backed by a pool of home loans.
  Homeowners' monthly payments "pass through" to the investor. A government
  agency (Fannie Mae, Freddie Mac or Ginnie Mae) guarantees the payments, so
  the investor bears interest-rate risk but almost no credit risk. Agency
  mortgage bonds are the largest holding in BNY's securities portfolio
  (Phase 4).
- **WAC and net coupon.** The loans' average interest rate is the WAC
  (weighted-average coupon). The investor receives a little less, the *net
  coupon*, because servicers and the agency take a fee. Tenorwise uses
  0.50 percentage point.
- **Level payment.** Each borrower pays the same amount every month. Early
  payments are mostly interest; later ones mostly principal.
- **Prepayment.** Borrowers can repay early, usually by refinancing when
  market mortgage rates fall below their own rate. The *refinancing
  incentive* is WAC minus today's mortgage rate.
- **CPR and SMM.** CPR (conditional prepayment rate) is the annualised
  fraction of the remaining balance repaid early. SMM is the monthly
  equivalent: 1 − (1 − CPR)^(1/12).
- **The S-curve.** Prepayments respond to the incentive in an S shape. When
  refinancing saves nothing, a few people still move house or sell (6% a
  year here). When the saving is large, almost everyone who can refinance
  does (40%). The steep middle is where speeds react most to rates. New
  loans prepay slowly at first, so speeds ramp up over 30 months of age.
- **Weighted average life (WAL).** On average, how many years until the
  principal comes back. It is short when borrowers refinance fast and long
  when they don't.
- **Negative convexity.** When rates fall, prepayments accelerate and hand
  back principal at par just when it is worth more than par, so the price
  gain is capped. When rates rise, prepayments slow and the investor is
  stuck with a below-market coupon for longer (*extension risk*). So the
  loss from a rate rise is larger than the gain from an equal fall: the
  opposite of an ordinary bond.
- **Current-coupon pool.** A pool whose coupon matches today's market and
  which trades near par. "A pool near current rates" means this (D-032).
- **Mortgage spread.** How much higher mortgage rates are than the 10-year
  Treasury yield: 2.14 percentage points on 16 November 2026 (Optimal Blue
  index 7.26% minus 5.12%). Each scenario's mortgage rate is its 10-year
  par yield plus this fixed spread.

### How the code implements it

- [tenorwise/instruments/mbs.py](tenorwise/instruments/mbs.py): `PrepaymentModel`
  (the S-curve and ramp, labelled stylized), `MortgagePool` (WAC, remaining
  term, age), `project()` (the monthly loop: level payment, interest,
  scheduled principal, prepayment), `price()` (discount the investor cash
  flows on the curve plus a spread) and `discount_spread_for_price()` (the
  spread that prices a pool at par).
- [tenorwise/curve/mortgage_spread.py](tenorwise/curve/mortgage_spread.py):
  OBMMIC30YF minus DGS10 on the latest date both have values, with no filling
  and a 7-day staleness limit. The pinned data is in
  [data/fixtures/fred_obmmic30yf_2026-11-17.json](data/fixtures/fred_obmmic30yf_2026-11-17.json).
- Risk comes from the same engine as bonds
  ([tenorwise/analytics/risk.py](tenorwise/analytics/risk.py)). The pool's
  price function reads the shocked curve's 10-year par yield, so every bump
  also changes prepayments. This is what makes effective duration
  "effective".
- [tenorwise/analytics/mbs_profile.py](tenorwise/analytics/mbs_profile.py):
  price, effective duration and convexity, average life and CPR across
  shifts from −300 to +300 bp, next to the Treasury bullet with the closest
  effective duration. Fields follow the `mbs.json` contract. Run with
  `uv run python -m tenorwise.analytics.mbs_profile`.

### Results on the pinned data (2026-11-16), computed by the engine

Pool: WAC 7.263% (today's mortgage rate), net coupon 6.763%, 36 months old,
324 months left. A discount spread of 162.1 bp prices it at 100. The
comparison is a 5.12% Treasury bullet of 7.5 years.

| Shift | CPR | Avg life | Pool price | Eff. duration | Treasury price |
|---|---|---|---|---|---|
| −300 bp | 39.9% | 1.95 y | 106.05 | 1.77 | 121.49 |
| −100 bp | 23.0% | 3.63 y | 103.65 | 0.56 | 107.03 |
| 0 | 7.6% | 8.95 y | 100.00 | 6.19 | 100.57 |
| +100 bp | 6.1% | 10.11 y | 93.87 | 6.09 | 94.56 |
| +300 bp | 6.0% | 10.18 y | 83.73 | 5.41 | 83.79 |

- **Negative convexity:** −137 at today's rates. The Treasury's is positive.
- **Asymmetry:** +3.65 at −100 bp against −6.13 at +100 bp.
- **Extension:** average life stretches from 2.0 to 10.2 years.
- **Capped upside:** at −300 bp the pool gains 6.0 points while the Treasury
  gains 20.9.

### Why this design, and what was rejected

- **Static valuation, as the plan specifies.** Project cash flows once per
  scenario, then discount. The industry standard is an option-adjusted
  spread (OAS) model that simulates thousands of rate paths. It values the
  borrower's option more accurately but is far harder to explain and test.
  Static valuation still shows negative convexity and extension, which is
  the purpose here.
- **A logistic S-curve with four parameters.** Each parameter has a plain
  meaning (floor, ceiling, steepness, midpoint) and can be drawn on a
  whiteboard. Real prepayment models add burnout, seasonality, turnover and
  cash-out refinancing.
- **Mortgage rate from Optimal Blue, not Freddie Mac** (D-031). Freddie Mac's
  terms forbid publishing its data or anything derived from it. Optimal
  Blue's index is daily, which also matches the Treasury curve's date.
- **"Current coupon" means priced at par** (D-032). Discounting at plain
  Treasury rates made the test pool a premium bond, and in static
  valuation that produced negative durations at −100 bp. Pricing at par is
  how the market defines a current-coupon pool.

### What would break it, and the behaviour at the edges

- **Prepayment floor (about +50 bp and beyond).** CPR sits at its 6% floor,
  the pool behaves like an ordinary bond, and its duration *falls* slowly as
  rates rise further: 6.36 at +50 bp, 5.41 at +300 bp. The plan's
  "effective duration rises as rates rise" holds only from −100 to +50 bp
  here (D-032).
- **Prepayment ceiling (deep rallies).** CPR approaches 40% and stops
  responding. Duration then rises again as rates fall, from 0.56 at
  −100 bp to 1.77 at −300 bp.
- **Premium pricing.** A pool priced well above par can show negative
  effective duration in static valuation (seen during testing with Treasury
  discounting). It is a property of the model, not of real mortgage bonds.
- The parameters are illustrative. A different k or x0 moves every number
  above.

### Interview questions

1. **Why do mortgage bonds have negative convexity?**
   Borrowers hold an option to repay at par. When rates fall they refinance,
   so the investor gets par back just when the bond is worth more. When rates
   rise they stay put, and the investor holds a below-market coupon for
   longer.
2. **What is extension risk?**
   As rates rise, prepayments slow and the bond's average life lengthens. In
   this model it goes from 9 years to over 10, which raises duration just
   when rates are hurting.
3. **Why is your valuation called "static", and what does that miss?**
   It projects one set of cash flows per scenario and discounts it. It
   ignores that rates are uncertain, so it misses the time value of the
   borrower's option. An OAS model would charge for that option.
4. **Why does the pool's duration fall again when rates rise a lot?**
   Prepayments can't fall below the floor (people still move house). Once
   they're there, the pool is effectively a fixed bond, and a fixed bond's
   duration falls as yields rise.
5. **Why didn't you use Freddie Mac's mortgage rate?**
   Its terms forbid publishing the data or derived products without a
   licence, and Tenorwise publishes derived figures. Optimal Blue's index
   via FRED carries no such notice, and it is daily, which lines up with the
   Treasury curve.
6. **What does the discount spread of 162 bp represent?**
   The extra yield over Treasuries at which this stylized pool prices at
   par. It is a calibration choice that makes the pool current-coupon, not a
   market OAS.

---

## Phase 4. Portfolio

### Finance concepts, in plain English

- **A bank's securities portfolio.** Besides lending, banks invest deposits
  in high-quality bonds: Treasuries, agency mortgage bonds, agency debt. They
  earn interest and can be sold or pledged for cash. BNY's portfolio is about
  $152 billion (10-Q, 30 Sept 2026).
- **AFS and HTM.** Each security is classified when bought:
  - *Available-for-sale (AFS)* securities might be sold. They are carried at
    market value, and their unrealized gains and losses go to **AOCI**
    (accumulated other comprehensive income), a part of shareholders' equity.
    A rate rise therefore reduces a bank's reported equity through its AFS
    book.
  - *Held-to-maturity (HTM)* securities are to be held until they mature.
    They are carried at amortized cost, and price moves do not touch equity,
    though the losses are still economically real and are disclosed.
- **Book yield.** The yield the bank locked in when it bought a security.
- **Amortized cost.** The security's remaining cash flows discounted at its
  book yield: what it is worth "at purchase terms". A bond bought at par
  stays at par.
- **Unrealized gain or loss.** Market value minus amortized cost. A bond
  bought at 2% when market yields are now 5% shows a large unrealized loss.
- **Why it matters.** When rates rose sharply in 2022, banks that had bought
  long, low-yield bonds in 2020–21 built up large unrealized losses. Those
  losses showed up in equity through AOCI (AFS) or sat off-balance-sheet
  (HTM). Measuring and hedging that exposure is what Tenorwise is for.

### How the code implements it

- [tenorwise/portfolio/sources.py](tenorwise/portfolio/sources.py) and
  [data/sources/bny_10q_3q26_investment_securities.json](data/sources/bny_10q_3q26_investment_securities.json):
  BNY's Note 2 table (page 52) and maturity and yield table (page 55),
  transcribed with citation and PDF SHA-256, and mapped into four sectors.
  Excluded: non-US government (needs foreign curves) and CLOs (floating
  rate), which are 27.2% of BNY's securities.
- [data/portfolio/positions.json](data/portfolio/positions.json): the 38
  approved positions (D-036). Each cites the BNY line and maturity bucket it
  is sized from.
- [tenorwise/portfolio/positions.py](tenorwise/portfolio/positions.py): turns
  the spec into instruments in $ millions. It solves the two mortgage-pool
  shares per class, sizes each position to its share of $10,000M, and
  computes amortized cost from the book yield.
- [tenorwise/portfolio/valuation.py](tenorwise/portfolio/valuation.py):
  `build_market_context` builds the 12 bumped curves once and calibrates the
  agency-mortgage spread. `value_portfolio` reprices every position, then
  aggregates by sector and class: sums for values and DV01s, market-value
  weights for duration and convexity, and amortized-cost share for `weight`.
- `uv run python -m tenorwise.portfolio [--positions]` prints the summary.

### Results on the pinned data (2026-11-16), computed by the engine

| | Amortized cost | Market value | Unrealized | Eff. duration | DV01 ($k/bp) |
|---|---|---|---|---|---|
| Portfolio | 10,000.0 | 8,648.6 | −1,351.4 | 4.48 | 3,876 |
| Treasuries | 3,184.3 | 3,010.9 | −173.5 | 2.84 | 855 |
| Agency mortgage (stylized) | 4,579.8 | 3,622.2 | −957.6 | 6.03 | 2,184 |
| Agency debt | 1,133.3 | 1,005.2 | −128.1 | 5.15 | 518 |
| IG corporates (proxy) | 1,102.5 | 1,010.3 | −92.2 | 3.16 | 319 |
| AFS | 6,410.0 | 5,779.0 | −631.0 | 4.17 | 2,409 |
| HTM | 3,590.0 | 2,869.6 | −720.4 | 5.11 | 1,467 |

(Amounts in $ millions.)

- **Book yields:** AFS averages 3.510% against BNY's 3.57%; HTM averages
  2.451% against 2.58%.
- **The mortgage sector's convexity is positive today (+67).** Every pool in
  the book has a WAC below today's 7.26% mortgage rate. The low-coupon
  2020–22 pools are far below it, so prepayments are near their floor and the
  pools behave like plain bonds. Negative convexity will show up in rally
  scenarios (Phase 5), when refinancing becomes worthwhile.
- **The AFS book's DV01 is $2.41M per bp.** That is the exposure the Phase 6
  hedges are sized against.

### Why this design, and what was rejected

- **Sizes and book yields come from the filing, not from judgment.** Every
  position points to a BNY line and maturity bucket; only the splits,
  maturities within buckets and pool vintages are design choices.
- **Bought at par.** Amortized cost then equals face, and the book yield is
  simply the coupon, which is easy to explain and to test. Rejected: random
  purchase prices with premium amortization histories, which would be
  invented detail.
- **The BNY comparison is a sanity check, not a target** (D-039). BNY's
  reported AFS losses are shrunk by fair-value hedge accounting on about
  $61B of par, and its real holdings differ from the stylized pools.
  Calibrating to its unrealized losses would bake those differences in.

### What would break it

- A new BNY filing with a different mix: re-transcribe and rerun the tests.
  The transcription tests catch typing errors through the filing's own
  arithmetic.
- Changing a pool's fixed share so that the solved shares fall outside
  0–100%. `load_positions` raises an error rather than producing an
  impossible pool.

### Interview questions

1. **What's the difference between AFS and HTM, and why does a bank care?**
   AFS is marked to market and its unrealized losses reduce equity through
   AOCI. HTM is carried at amortized cost, so losses don't hit reported
   equity. But HTM cannot be sold without consequences, and the losses are
   still economically real.
2. **What are amortized cost and unrealized loss?**
   Amortized cost is the bond's value at the yield it was bought at.
   Unrealized loss is how far today's market value is below that, because
   rates have risen since purchase.
3. **How did you build a portfolio that resembles BNY's?**
   I transcribed Note 2 of its 10-Q and mapped each line into four sectors.
   I sized each position from a specific line and maturity bucket and used
   BNY's disclosed yields as book yields. The tests check the transcription
   against the filing's own totals.
4. **Your model shows larger losses than BNY reports. Why?**
   BNY hedges about $61B of AFS securities with swaps under fair-value hedge
   accounting, which offsets much of the reported AFS loss, and its actual
   holdings differ from the stylized pools. Rates were actually higher on
   BNY's reporting date, so it isn't timing.
5. **Why is the mortgage book positively convex today?**
   The pools were mostly made when mortgage rates were 3–4%. Today's rate is
   7.26%, so nobody refinances. Prepayments sit at their floor and the pools
   behave like ordinary bonds. Convexity turns negative only if rates fall
   far enough for refinancing to pay.
6. **Why is the IG corporates sleeve called a proxy?**
   BNY holds almost no corporate bonds. That sleeve stands in for its other
   fixed-rate credit holdings, mostly foreign covered bonds, modelled as US
   dollar bullets with a 100 bp spread.

---

## Phase 5. Scenarios

### Finance concepts, in plain English

- **Scenario analysis.** Instead of a single sensitivity number like DV01,
  ask "what if rates did this?" and reprice everything. Tenorwise's
  scenarios are instantaneous: the curve jumps, then holds still.
- **Parallel shift.** Every maturity moves by the same amount (±100 or
  ±200 bp).
- **Steepener and flattener.** The curve's *shape* changes. In a *bear
  steepener* rates rise (bad for bondholders, hence "bear"), long rates most:
  +25 bp up to 2 years rising to +100 bp at 30. In a *bull flattener* rates
  fall, long rates most. A portfolio hedged only for parallel moves can still
  lose here.
- **2022 replay.** During 2022 the Federal Reserve raised rates from near
  zero, and Treasury yields rose by +406 bp at 1 month, +368 bp at 2 years,
  +236 bp at 10 years and +207 bp at 30 years (FRED, 31 Dec 2021 to
  30 Dec 2022). Replaying those moves on today's curve asks: what would a
  year like 2022 do to this book now?
- **AOCI impact.** The part of a scenario's loss that reaches reported
  equity: the change in value of AFS securities, before tax.
- **HTM change "not recognized".** The HTM part of the loss is just as real
  economically, but the accounts keep HTM at amortized cost, so it doesn't
  show in equity. Reporting it separately shows what the accounting hides.
- **Carry.** What the book earns by simply holding its bonds: interest
  income over the next 12 months, at the book yields. For mortgage pools the
  balance shrinks as borrowers repay, so faster prepayment in a rally means
  less interest. No funding cost, no reinvestment.

### How the code implements it

- [tenorwise/scenarios/definitions.py](tenorwise/scenarios/definitions.py): the
  seven presets. The steepener and flattener are the key-rate tents scaled by
  25, 50, 75 and 100 bp, so in between they move in straight lines (3y
  +33.3, 7y +60, 20y +87.5).
- [tenorwise/scenarios/replay.py](tenorwise/scenarios/replay.py) and
  [data/fixtures/fred_treasury_par_replay_2022.json](data/fixtures/fred_treasury_par_replay_2022.json):
  the 2022 change per tenor from the exact dates, with no filling.
- [tenorwise/scenarios/revaluation.py](tenorwise/scenarios/revaluation.py):
  `run_scenario` applies the shock through the same `apply_shock` used
  everywhere. It reprices every position with spreads held fixed, splits each
  change into AOCI (AFS) and not-recognized (HTM), and aggregates by sector
  and class.
- [tenorwise/scenarios/carry.py](tenorwise/scenarios/carry.py): monthly
  amortized cost × book yield / 12, over 12 months. For mortgage pools it
  uses the balance under the scenario's prepayments.
- `uv run python -m tenorwise.scenarios [--by-sector]` prints the
  seven-scenario table.

### Results on the pinned data (2026-11-16), computed by the engine

Base market value $8,648.6M; base 12-month carry $298.3M.

| Scenario | Change in value | AOCI (AFS) | HTM, not recognized | Carry |
|---|---|---|---|---|
| +100 bp | −370.6 (−4.3%) | −230.8 | −139.8 | 298.3 |
| −100 bp | +402.2 (+4.7%) | +248.0 | +154.2 | 297.7 |
| +200 bp | −710.4 (−8.2%) | −443.5 | −266.9 | 298.3 |
| −200 bp | +819.8 (+9.5%) | +494.7 | +325.1 | 295.2 |
| Bear steepener | −233.1 (−2.7%) | −138.8 | −94.4 | 298.3 |
| Bull flattener | +247.9 (+2.9%) | +146.2 | +101.7 | 298.0 |
| 2022 replay | −923.1 (−10.7%) | −589.3 | −333.8 | 298.3 |

($ millions, pre-tax.)

- **A ±1 bp scenario matches DV01 within 0.045%** (the test allows 1%).
- **The 2022 replay is the worst scenario:** −10.7% of market value, with
  $589M hitting AOCI.
- **The mortgage sleeve is positively convex today.** It gains 227.6 at
  −100 bp but loses 206.4 at +100 bp. Most pools are 2020–22 vintages far
  below today's 7.26% mortgage rate, so refinancing never pays. Negative
  convexity appears only near the money: the 2025 pool (WAC 7.00%) gains
  10.6 and loses 12.1. The plan's test was reworded to test that pool
  (D-042).
- **Carry barely moves.** Coupons are fixed and there's no reinvestment. In
  rallies it falls slightly (−$3.1M at −200 bp) as the near-the-money pools
  prepay. Rising rates don't raise carry because the book holds its old
  bonds and reinvests nothing.

### Why this design, and what was rejected

- **One shock mechanism.** Every scenario goes through `apply_shock`, so
  scenarios, durations and key-rate measures agree with each other. That is
  why ±1 bp reproduces DV01 to 0.045%.
- **Full repricing rather than a duration estimate.** Large moves need the
  convexity and prepayment effects; Phase 2 showed duration alone misses by
  up to 16% at 100 bp.
- **The replay uses actual changes from FRED,** not a hand-built 2022 shape,
  and fails rather than fills if a date is missing.
- **Carry as income at the book yield,** as the plan specifies. It is the
  number a bank's net interest income forecast starts from, and it is simple
  to explain. Rejected: total return including price changes, which mixes in
  the scenario's mark-to-market already shown separately.

### What would break it

- Scenarios that push par yields below 0%. The floor binds and the result is
  flagged (tested with −450 bp). Scenario figures then reflect the floor,
  not the shock.
- A missing FRED value on 31 Dec 2021 or 30 Dec 2022: the replay fails
  loudly.
- Reading carry as a forecast of earnings. It ignores funding cost,
  reinvestment and new purchases.

### Interview questions

1. **Why report AOCI and HTM separately?**
   AFS losses reduce reported equity through AOCI. HTM losses don't show in
   the accounts but are just as real: if the bank had to sell, it would
   realize them. Showing both makes the hidden part visible.
2. **What does the 2022 replay tell you?**
   Applying 2022's actual rate rises to today's book would cut market value
   by 10.7%, $923M. $589M of that would hit equity through AOCI and $334M
   would sit unrecognized in HTM.
3. **Why does a bear steepener matter if you already know the DV01?**
   DV01 assumes every rate moves together. In a steepener long rates rise
   more, so a book with long-dated holdings loses more than its 2-year
   exposure suggests, and a hedge sized on DV01 alone can be left exposed.
4. **Why didn't the mortgage sleeve show negative convexity?**
   Most of the pools were made at 2.5–4.5% mortgage rates. At 7.26% today,
   even a 2-point fall doesn't make refinancing worthwhile, so they behave
   like plain bonds. The negatively convex part is the pool close to today's
   rate.
5. **Why doesn't carry rise when rates rise?**
   The book's coupons are fixed and the model reinvests nothing, so income
   on existing holdings is unchanged. Only in rallies does carry fall,
   because borrowers repay mortgages faster.
6. **Is ±1 bp consistent with DV01?**
   Yes, within 0.045%, because scenarios and DV01 use the same shock
   mechanism and full repricing.
