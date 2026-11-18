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
