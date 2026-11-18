# Decision log

The main design choices, the alternatives rejected, and why. One entry per
decision, newest at the bottom. Changes to PLAN.md are recorded here too.

---

## D-000. Plan change: design-handoff figures are placeholders (Phase 11)

- **Date:** 2026-11-17, before Phase 0 started
- **Change:** PLAN.md Phase 11 gained the rule "Every figure in the design handoff is an invented placeholder. Never copy one into the app, a fixture or a document; all displayed numbers come from the engine."
- **Who:** made by the project owner directly in PLAN.md; recorded here as the plan requires.
- **Why:** a design mock-up contains realistic-looking numbers. Copying one into the app would show a figure that no calculation produced.

## D-001. Hosting layout: static Vite site plus one Python function at `api/index.py`

- **Phase:** 0
- **Decision:** one Vercel project. Vite builds the static frontend. FastAPI runs as a file-based Python function at `api/index.py`, and `vercel.json` rewrites `/api/*` to it. This is the layout PLAN.md section 5 specifies.
- **Alternatives rejected:**
  - *Vercel Services (beta):* separate frontend and backend services in one project. Vercel's docs (read 2026-11-17) recommend it for "a Python backend alongside another framework", and they describe the `/api` directory as supported for "existing projects". The plan says to try the `/api` layout first and to ask before switching to Services. A beta feature is also more to explain and more likely to change.
  - *FastAPI preset serving the frontend:* FastAPI's `app.frontend()` serves the built site and Vercel promotes the files to its CDN. This couples the static site to the Python app's deployment and routing.
- **Status:** confirmed by the Phase 0 deploy (2026-11-18 UTC). The build step ran Python, the function read the files the build wrote, numpy and scipy worked in the function, and pandas and QuantLib were not installed. Services is not needed. Evidence is in NOTES.md, Phase 0.

## D-002. Pin the Vercel framework to Vite in `vercel.json`

- **Phase:** 0
- **Decision:** set `"framework": "vite"` explicitly.
- **Why:** Vercel's Python docs say a detected Python framework preset "takes precedence over file-based functions" and then handles all requests. The repo root has a `pyproject.toml` listing FastAPI. Without the pin, Vercel could treat the whole project as a FastAPI app, and the static frontend would stop being served.

## D-003. pandas and QuantLib are dev-only dependencies; neither is installed in the function

- **Phase:** 0
- **Decision:** `[project.dependencies]` lists only what the deployed function needs: fastapi, httpx, numpy, pydantic and scipy. pandas, QuantLib, pytest and uvicorn live in the `dev` dependency group.
- **Alternative rejected:** list pandas as a runtime dependency and rely on a test to keep it off the request path. That meets the letter of ground rule 6, but pandas would still be installed in production. With this split it is not even installed there, so it cannot be imported by accident. The import-isolation test stays as a second guard.
- **Evidence:** `tests/api/test_import_isolation.py`; the deployed `/api/deploy-check` reports whether pandas and QuantLib are installed.

## D-004. The build-time Python environment lives outside the project directory

- **Phase:** 0
- **Decision:** `scripts/vercel_build.sh` runs the snapshot build with `UV_PROJECT_ENVIRONMENT` set to a folder in `/tmp`, using `--no-dev`. `vercel.json` also excludes `web/`, `tests/`, `docs/`, `scripts/` and `.venv/` from the function bundle.
- **Why:** Vercel bundles every file it can reach from the project into a Python function. A virtual environment created inside the project would be bundled too, adding hundreds of MB.

## D-005. The function reads the snapshot files on every request

- **Phase:** 0
- **Decision:** `tenorwise/snapshot/store.py` opens and parses the JSON file on each call. There is no module-level cache.
- **Alternative rejected:** caching the parsed files in memory (for example with `functools.lru_cache`). It is faster on warm invocations, but it holds state between requests, which ground rule 7 forbids. The files are small, so the cost is negligible.

## D-006. The provider probe uses raw HTTP, not the OpenAI SDK

- **Phase:** 0
- **Decision:** `scripts/probe_llm.py` calls `POST /v1/chat/completions` with httpx.
- **Why:** the probe exists to record what the provider actually returns. Raw JSON shows every field, including undocumented ones such as `prompt_tokens_details.cached_tokens`. It also leaves no hidden SDK retries or SDK-side typing of Sail-specific values such as `service_tier: "asap"`. The Phase 8 provider will make the same choice for the same reasons, unless something found then argues otherwise.

## D-007. Retry policy: refused-before-inference errors only

- **Phase:** 0 (probe); applies again in Phase 8
- **Decision:** retry 429 and 503 errors with code `model_capacity_unavailable` or `service_overloaded`, waiting at least `Retry-After` and backing off exponentially with jitter. Do not retry timeouts or other 5xx errors, because the request may already have started and could be billed twice.
- **Note:** PLAN.md names 429 and 503 `model_capacity_unavailable`. Sail's `retries.md` (read 2026-11-17) also lists 503 `service_overloaded` as refused "before accepting a request". It was included in the probe. The owner approved adding it on 2026-11-17 (D-014).

## D-008. A temporary `/api/deploy-check` endpoint instead of extra health fields

- **Phase:** 0
- **Decision:** a separate Phase 0 endpoint reports the build-written file as read inside the function, the numpy and scipy versions plus a scipy calculation run in the function, and whether pandas and QuantLib are installed. It will be removed in Phase 7, when the real snapshot exists.
- **Alternative rejected:** adding these fields to `/api/health`. Its fields are part of the interface contract in PLAN.md section 8.

## D-009. Assistant tool-call turns are sent back without `reasoning_content`

- **Phase:** 0
- **Decision:** when replaying an assistant turn, send only `role`, `content` and `tool_calls`.
- **Why:** Sail's request schema for chat messages sets `additionalProperties: false`, so other fields are not allowed. The probe's tool round trips passed for all three models this way.

## D-010. Pinned tool versions and no global installs

- **Phase:** 0
- **Decision:** scaffold with `create-vite@9.3.1` and run the Vercel CLI as `npx vercel@65.12.1`. Neither is installed globally.
- **Accepted risk:** `npm audit` reports a high-severity ReDoS advisory (GHSA-fc5q-39xc-vjpf) in `picomatch`. It is reached only through Vite's build tooling and does not ship in the browser bundle. npm's only offered fix downgrades Vite to 6.2.7, a breaking change. Revisit when Vite ships a patched dependency.

## D-011. Git SHA comes from a build variable for CLI deploys

- **Phase:** 0
- **Decision:** `scripts/build_snapshot.py` reads `TENORWISE_GIT_SHA`, then `VERCEL_GIT_COMMIT_SHA`, then `git rev-parse`. CLI deploys pass `--build-env TENORWISE_GIT_SHA=<sha>`.
- **Why:** a CLI deploy does not upload `.git` (`.vercelignore`), and `VERCEL_GIT_COMMIT_SHA` is set only for Git-connected deploys. The SHA is not a secret.

## D-012. The first deployment went to production, not a preview

- **Phase:** 0
- **What happened:** the approved action was a preview deploy. Vercel assigns a project's *first* deployment to production regardless, and the CLI said so only afterwards: "This is the project's first deployment, so it was assigned to production. Future deployments will be preview deployments unless you use --prod." The skeleton is therefore live at `https://tenorwise.vercel.app`, which is publicly reachable. Vercel's default protection covers deployment URLs, not the production domain.
- **Exposure:** the Phase 0 placeholder page, `/api/health` and `/api/deploy-check`. No environment variables are set on Vercel, and no key was uploaded (`vercel deploy --dry` showed `.env` and `.env.local` excluded).
- **Decision:** reported to the owner, who decided on 2026-11-17 to **keep** it. The deployment holds nothing sensitive, and it reserves the `tenorwise.vercel.app` name. Every later deploy uses the CLI's default preview target, and production deploys happen only after asking (Phase 12).

## D-013. `vercel link` side effects

- **Phase:** 0
- **What happened:** `vercel link` created `.env.local` holding a short-lived `VERCEL_OIDC_TOKEN`. It also appended `.vercel` and `.env*` to `.gitignore`. That appended `.env*` would have overridden the `!.env.example` exception and ignored the example file.
- **Decision:** reverted the `.gitignore` edit. The existing rules already ignore `.vercel/` and `.env.*` (including `.env.local`), and `.vercelignore` excludes `.env.*` from uploads.

## D-014. Plan change: retry 503 `service_overloaded` as well

- **Date:** 2026-11-17, approved by the owner after Phase 0
- **Change:** PLAN.md sections 4 and 9 now list 503 `service_overloaded` next to 429 and 503 `model_capacity_unavailable` as retryable.
- **Why:** Sail's `retries.md` says `service_overloaded` is returned "before accepting a request in any service tier". Like the other two, it cannot have started inference, so a retry cannot double-charge.

## D-015. The FRED fixture stores raw responses, and its fetch date is the build date

- **Phase:** 1
- **Decision:** `data/fixtures/fred_treasury_par_2026-11-17.json` stores FRED's JSON responses verbatim for a 45-day window, with no API key. The fetch date (`as_of`) stands in for the build date in the 7-day staleness check. Pinning a new fixture is a code change to `PINNED_FIXTURE`; the update script never re-pins.
- **Alternative rejected:** storing a cleaned table of the 11 yields. Tests would then skip the real parsing path, including the "." handling.

## D-016. FRED error messages are built locally and scrubbed of the key

- **Phase:** 1
- **Decision:** the FRED key can only travel as a query parameter, so any message containing the request URL would leak it. `fetch_observations` never reuses httpx's exception text that may include URLs. It builds its own message, removes the key from it, and raises with `from None` so the original exception is not displayed.
- **Evidence:** `tests/unit/test_fred.py::test_fetch_errors_never_contain_the_api_key` (HTTP 500, an HTTP 400 that echoes the key, and a network error).

## D-017. `numpy.interp` for both interpolation and the key-rate tents

- **Phase:** 1
- **Decision:** `numpy.interp` is linear between points and flat beyond the ends, which is exactly the plan's rule. The same function builds each key-rate tent by interpolating a one-hot vector over the nodes 2, 5, 10 and 30. The four tents therefore add up to 1 by construction.
- **Alternatives rejected:** `scipy` interpolators or splines. Smoother forward rates, but not what the plan specifies and harder to explain. Hand-written piecewise tent formulas would also need their own tests for the sum-to-1 property.

## D-018. The QuantLib benchmark conventions, and a tolerance fixed in advance

- **Phase:** 1
- **Decision:** QuantLib uses 30/360 day counts from a reference date on the 15th of a month, so n months is exactly n/12 years. It uses no calendar, no adjustment and zero settlement lag. Deposits model tenors of 6 months and under; par fixed-rate bonds model the longer tenors. The curve is `PiecewiseLinearZero`. The tolerance (1e-10 in rate) was set before the first run.
- **Measured:** maximum difference 1.5e-13, at the 3-month point, on the 2026-11-16 curve.

## D-019. Shocks act on par yields, and the curve is fully rebuilt

- **Phase:** 1
- **Decision:** as the plan specifies, every shock adds basis points to the 11 par yields and calls the same `bootstrap()`.
- **Consequence:** a key-rate bump at one tenor moves zero rates at other tenors through the bootstrap. On the pinned curve, +25 bp on the 10-year tent lowers the 30-year zero rate by 13.6 bp. This is documented in ASSUMPTIONS.md (A-06) and LIMITATIONS.md rather than "fixed", because shocking zero rates directly would be a different model from the one the plan specifies.

## D-020. Floor at 0% applies to shocked par yields only

- **Phase:** 1
- **Decision:** the floor applies after the shock is added and before the rebuild. `ShockedCurve.floor_bound` and `floored_tenor_months` report it. Unshocked market data is never altered.

## D-021. Flat-curve test split because of the short-end convention

- **Phase:** 1
- **Issue:** PLAN.md asks for "a flat par curve gives a flat zero curve at the equivalent continuous rate". The plan also prices tenors of 6 months and under with simple interest, and those two specifications conflict at 1 and 3 months. At a flat 4%, those zero rates come out 3.3 bp and 2.0 bp above the 6-month-and-beyond level (calculated from the formulas).
- **Done:** implemented the plan's formula as written. The test checks flatness from 6 months out, and checks the short end against its own simple-interest formula. No tolerance was loosened.
- **Option for the owner:** treat the short end as semiannual too, DF = (1 + y/2)^(-2T). The zero curve would then be flat everywhere for a flat par curve, matching the "semiannual bond-equivalent" treatment of every other tenor. That is a plan change and needs approval.
- **Resolved 2026-11-17:** the owner chose to keep the plan's simple-interest formula. Treasury quotes bills of 6 months and under on a simple-interest bond-equivalent basis, so the formula follows market convention. The test wording in PLAN.md was changed to match (D-023).

## D-022. FRED attribution and terms

- **Phase:** 1
- **Read on 2026-11-17:** the FRED API Terms of Use require the notice "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis". For an application used by others, they also require a link to the Terms of Use and a statement in the application's own terms that its users agree to be bound by them. None of the 11 series' notes contain the word "Copyright", so no third-party restrictions apply to them.
- **Done now:** the notice is printed by the curve CLI and the fixture script, and appears in README.md.
- **Approved 2026-11-17, for the interface footer (Phase 7 placeholder, Phase 11 design):** "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis. By using Tenorwise you agree to the FRED® API Terms of Use", with the last words linking to https://fred.stlouisfed.org/docs/api/terms_of_use.html.
- **Still open:** the terms require a privacy policy if the application collects information about its users. This is to be raised in Phase 8 with the hashed-IP rate limits.

## D-023. Plan change: Phase 1 flat-curve test reworded

- **Date:** 2026-11-17, approved by the owner
- **Change:** PLAN.md Phase 1 now reads "a flat par curve gives a flat zero curve at the equivalent continuous rate from 6 months out, and at 1 and 3 months each zero rate matches its own simple-interest instrument". The engine's formula is unchanged.
- **Why:** see D-021. The original wording could not hold under the plan's own short-end formula.


## D-024. Plan change: the formula-vs-bump DV01 test runs on a flat curve, and the real-curve gap is explained (option A)

- **Date:** 2026-11-17, approved by the owner
- **Issue:** the plan's test "formula DV01 matches bump-and-reprice within 0.1%" failed for 65 of 85 zero-spread bonds on the real curve, by up to +4.45% (20-year zero). On a synthetic flat 5% curve, all 85 agree within 0.012%. On the real curve, the gap equals the bond's own-yield move per 1 bp of par yields, to 5 decimal places. Bootstrapping an upward-sloping curve amplifies parallel par shifts at long maturities.
- **Change:** PLAN.md Phase 2 now reads "formula DV01 matches bump-and-reprice within 0.1% on a flat par curve; on the real curve, the gap equals the bond's own-yield move per 1 bp of par yields, within 0.1%". The tolerance is unchanged.
- **Alternatives rejected:**
  - (B) Yield-based DV01 everywhere. Inconsistent with Phase 5, where scenarios move par yields, so DV01 would no longer predict scenario P&L.
  - (C) Shock zero rates instead of par yields. That replaces the shock mechanism in PLAN.md section 6, a large change.
- **Consequence:** headline duration and DV01 stay curve-based; `mod_duration` is shown and labelled as yield-based.

## D-025. Key-rate bumps are ±1 bp

- **Phase:** 2
- **Decision:** the plan says "reprice under each tent" without a size. ±1 bp matches the DV01 bump, so key-rate DV01s read directly as dollars per bp in each bucket.
- **Measured:** the four key-rate durations sum to the ±25 bp effective duration within 0.096% at worst on the 170-bond grid (the plan allows 0.5%).

## D-026. One bump-and-reprice risk engine for every instrument

- **Phase:** 2
- **Decision:** `build_risk_curves()` builds the 12 bumped curves once; `risk_measures(price_fn, curves)` reprices any instrument given only a function from curve to value. Durations are `None` when the base value is zero, as for a swap at inception; DV01 is still reported.
- **Alternative rejected:** analytic duration and convexity formulas for each instrument. They do not exist in closed form for mortgage pools, whose cash flows depend on rates, and they would need separate tests for each instrument.

## D-027. Yield-based measures live in `analytics/yield_measures.py`

- **Phase:** 2
- **Decision:** yield, Macaulay and modified duration and convexity are functions of a cash-flow stream, not methods tied to one bond class. Mortgage cash flows can reuse them in Phase 3.

## D-028. QuantLib bond benchmark: conventions and tolerances fixed in advance

- **Phase:** 2
- **Decision:** QuantLib prices each bond on Tenorwise's own zero curve, rebuilt as `ql.ZeroCurve` (linear, continuous). It uses 30/360 from the 15th of a month, a backward semiannual schedule whose first accrual date is on or before the reference date, and `ZeroSpreadedTermStructure` for the spread. QuantLib's yield solver accuracy is set to 1e-12. Tolerances, set before the first run: price 1e-9 per 100 face, yield 1e-10, durations 1e-8 years, convexity 1e-6.
- **Measured (170 bonds):** price 1.4e-13, yield 7.1e-16, durations 5.0e-14, convexity 2.0e-12. Written to `docs/evidence/quantlib_report.json` by `scripts/quantlib_report.py`.

## D-029. Benchmark tests skip only when QuantLib itself is missing

- **Phase:** 2
- **Issue found:** `pytest.importorskip("tests.benchmark.quantlib_bonds")` would turn *any* import error in Tenorwise's own code into a silent skip. It did exactly that before the bond module existed.
- **Fix:** skip on `importorskip("QuantLib")` only, then import the helper normally, so a bug fails loudly.

## D-030. "Duration plus convexity predicts a 100 bp reprice closely" means within 2.5% of the change

- **Phase:** 2
- **Decision:** the plan gives no number. The error of a duration-plus-convexity estimate is the third-order term, largest for the longest zero-coupon bond. For a continuously compounded 30-year zero at 100 bp it is about 1.7% of the change (calculated). The threshold, fixed before the first run, is 2.5% of the actual change, and adding convexity must also beat duration alone.
- **Measured:** worst case 1.54% (30-year zero, +100 bp). Duration alone was off by up to 15.9%.

## D-031. Plan change: mortgage rate from Optimal Blue (OBMMIC30YF), not Freddie Mac (MORTGAGE30US)

- **Date:** 2026-11-17, approved by the owner
- **Issue:** FRED's notes for MORTGAGE30US say "Copyright, 2016, Freddie Mac. Reprinted with permission." Freddie Mac's terms (https://www.freddiemac.com/terms, read 2026-11-17) say data is for "internal business purposes or your own personal use only" and "You may not redistribute Data, publish Data, or commercially exploit Data or derived products/services without a separate written agreement or license". The mortgage spread drives every mortgage-bond figure Tenorwise publishes, and a fixture in a public repository would redistribute the data.
- **Change:** mortgage spread = latest OBMMIC30YF (Optimal Blue 30-Year Fixed Rate Conforming Mortgage Index, via FRED) minus DGS10 on the same date. FRED's notes for OBMMIC30YF contain no copyright notice. Optimal Blue's own page returned HTTP 403 to an automated request, so the owner checked its terms in a browser and found them acceptable for this use. Attribution: "Optimal Blue Mortgage Market Indices (OBMMI™), via FRED".
- **Side benefit:** OBMMIC30YF is daily, so the spread uses the same date as the Treasury curve; the weekly Freddie Mac series would have used an earlier Thursday.
- **Alternatives rejected:** (B) asking Freddie Mac for written permission, which is slow and uncertain; (C) a fixed illustrative spread, which drops a real market input.
- **No Freddie Mac data was fetched or stored** beyond reading the series metadata.

## D-032. Plan change: Phase 3 test definitions

- **Date:** 2026-11-17, approved by the owner
- **Issue:** with the test pool discounted at plain Treasury rates, a pool whose WAC equals today's mortgage rate is a premium bond. At synthetic spreads it priced at 102.9 to 109.4. That produced negative effective durations at −100 bp, a mechanical result of static valuation. Separately, effective duration rises with rates only while prepayments respond. Once CPR reaches its 6% floor, the pool behaves like a fixed bond and its duration drifts down.
- **Change:** "a pool near current rates" means WAC equal to the current mortgage rate *and* discounted at the spread that prices it at par on the base curve, which is the market's sense of a current-coupon pool. The gain-versus-loss test uses that pool. "Effective duration rises as rates rise" is tested from −100 to +50 bp; the behaviour beyond that is documented in NOTES.md and LIMITATIONS.md.

## D-033. The demonstration pool is a current-coupon pool priced at par

- **Phase:** 3
- **Decision:** `mbs_profile` and the Phase 3 tests use a pool with WAC equal to today's mortgage rate, 36 months old with 324 months left. It is discounted at the spread found by `discount_spread_for_price` (162.1 bp on 16 Nov 2026). The profile covers −300 to +300 bp in 50 bp steps, next to the Treasury bullet whose effective duration is closest at base (5.12%, 7y 6m).
- **Why:** it is the most informative single pool, sitting at the knee of the S-curve, and matches the market meaning of "near current rates" (D-032). The portfolio's actual pools are chosen in Phase 4.

## D-034. Fixture script never overwrites; one fixture file per dataset

- **Phase:** 3
- **Decision:** `scripts/update_fred_fixture.py --dataset treasury|mortgage|all` writes `fred_treasury_par_<date>.json` and `fred_obmmic30yf_<date>.json`, and refuses to overwrite existing files without `--force`. When the mortgage fixture was added, the pinned Treasury fixture stayed byte-identical (checked by checksum).

## D-035. The CPR reported for a pool is its first projected month's CPR

- **Phase:** 3
- **Decision:** the `cpr` field in profiles (and later `mbs.json`) is the CPR in month 1 of the projection. For a seasoned pool (36 months or more) it equals the long-run CPR, because the ramp is complete.

## D-036. Position list approved: sizes and book yields from BNY's filing

- **Date:** 2026-11-17, approved by the owner
- **Decision:** 38 positions in `data/portfolio/positions.json`. Each is sized as a share of a specific BNY line and maturity bucket (10-Q, printed page 55), scaled so total amortized cost is $10,000M. Each bond's book yield is BNY's disclosed yield for that line and bucket. Bonds are assumed bought at par (coupon = book yield) with whole half-year maturities, so there is no accrued interest. Mortgage pools are bought at par (book yield = bond-equivalent yield of the net coupon). Two pool shares per class are solved so the line's average book yield equals BNY's disclosed figure (3.97% AFS, 2.69% HTM).
- **Design choices, not data:** splits within a bucket, maturities (including those for lines BNY reports without maturity buckets), pool vintages, WACs and ages, and the fixed pool shares.
- **Book-yield averages kept as computed (owner chose not to nudge):** AFS 3.51% against BNY's 3.57%, HTM 2.45% against 2.58%. The gap comes mainly from the lines the plan excludes, CLOs at 4.87% and 5.01%.

## D-037. Sector spreads

- **Date:** 2026-11-17, approved by the owner
- **Decision:** Treasuries 0 bp. Agency mortgage bonds: recalibrated on every build so the stylized current-coupon pool prices at par (162.1 bp on 16 Nov 2026). Agency debt 25 bp and IG corporates proxy 100 bp, both illustrative, because no non-copyrighted public source was found.
- **Known effect:** in static valuation the agency-mortgage spread absorbs the cost of the prepayment option, which is largest for current-coupon pools. Applied to low-coupon pools it overstates their discount (LIMITATIONS.md).

## D-038. Weight basis

- **Date:** 2026-11-17, approved by the owner
- **Decision:** as in PLAN.md's table, BNY weights combine AFS at fair value with HTM at amortized cost. Tenorwise applies them as the model book's amortized cost.

## D-039. BNY's unrealized losses are a sanity check, not a calibration target

- **Date:** 2026-11-17, approved by the owner
- **Finding:** on the 16 Nov 2026 curve the model book shows −13.5% unrealized (HTM mortgage bonds −23.9% against BNY's −12.0%; AFS Treasuries −5.1% against −0.8%).
- **Explanations, checked where possible:** (1) not the date: Treasury yields were *higher* on BNY's reporting date of 30 Sep 2026 (10-year 5.29% against 5.12%); (2) BNY applies fair-value hedge accounting to about $61B of AFS par, which moves amortized cost with rates and shrinks reported AFS losses; (3) BNY's actual holdings differ, for example 15-year pools and premium purchases; (4) stylized low-coupon pools are long, with an average life of about 8.7 years at the 6% CPR floor, and the single mortgage spread over-discounts them. Even at a 0 bp spread a 2.5% pool prices at 83.1, against 88.0 for BNY's HTM agency mortgage bonds.
- **Decision:** document the comparison; do not calibrate to it.

## D-040. Plan fact correction: BNY's maturity and yield table is on printed page 55

- **Phase:** 4
- **Finding:** PLAN.md section 4 places the 3.57% and 2.58% yields in "the same note" as the page 52 table. They are in Note 2, but on printed page 55. The figures themselves match. The source file cites page 55.

## D-041. Portfolio aggregation conventions

- **Phase:** 4
- **Decision:** amounts are in $ millions and DV01 is in $ millions per bp internally. Values, amortized cost, unrealized, DV01 and key-rate DV01s are sums. Duration and convexity are market-value-weighted. `weight` is the share of amortized cost, the basis of the BNY mapping. The contract's `convexity` field is *effective* convexity, so mortgage pools can show negative values. `mod_duration` is yield-based for every position; for mortgage pools it uses the base-scenario projected cash flows at the pool's own yield.
- **Alternative rejected:** yield-based convexity in the contract. For a mortgage pool it is always positive and hides the prepayment effect.

## D-042. Plan change: the Phase 5 negative-convexity test applies to the near-the-money pool

- **Date:** 2026-11-17, approved by the owner (option A)
- **Finding:** on the approved BNY-like portfolio at 16 Nov 2026 rates, the agency mortgage sleeve gains $227.6M at −100 bp and loses $206.4M at +100 bp, so it is positively convex as a whole. 89% of the sleeve is 2020–22 pools whose WACs are 3.3 to 4.8 points below today's 7.26% mortgage rate, so even a 2-point rally does not make refinancing worthwhile and they behave like plain bonds. Negative convexity appears only near the money. The 2025 pool (WAC 7.00%) gains 10.6 and loses 12.1 at ±100 bp; the 2023 pool (6.50%) turns negative at ±200 bp.
- **Change:** PLAN.md Phase 5 now tests "the near-the-money mortgage pool (WAC within 0.5 percentage point of today's mortgage rate) gains less at −100 than it loses at +100". The whole sleeve's asymmetry is reported, not asserted. Phase 3's current-coupon pool test still covers the textbook case.
- **Alternatives rejected:**
  - (B) Adding current-coupon pools would contradict the approved BNY book yields (D-036).
  - (C) Changing the prepayment parameters would not move pools 3 to 5 points out of the money, and the parameters are fixed by the plan.

## D-043. Carry for mortgage pools uses the book yield on the running balance

- **Phase:** 5
- **Decision:** carry = sum over 12 months of (amortized cost at the start of the month × book yield / 12). For par-bought pools, amortized cost is the balance under the scenario's prepayments. One formula covers bonds and pools. For bullet bonds it reduces exactly to amortized cost × book yield × min(12, months left)/12 (tested).
- **Alternative rejected:** the pool's net interest received (balance × net coupon / 12). It differs from the plan's "amortized cost times book yield" only by the monthly-to-semiannual compounding conversion, but it would need a second formula.

## D-044. The 2022 replay fixture holds raw FRED responses around both dates

- **Phase:** 5
- **Decision:** `data/fixtures/fred_treasury_par_replay_2022.json` stores the 11 series' raw responses for 24 Dec 2021 to 3 Jan 2022 and 23 Dec 2022 to 3 Jan 2023. The shock uses only the exact plan dates, and all 11 series have values on both. Measured shock: +406, +436, +457, +434, +368, +325, +273, +252, +236, +220, +207 bp (1M to 30Y). H.15 data, no copyright notice.

## D-045. ASC 815 check: HTM interest-rate risk cannot be the hedged risk (current GAAP)

- **Phase:** 6, checked 2026-11-17 before any hedging code, as PLAN.md section 4 requires
- **Primary source:** FASB, *Accounting Standards Update No. 2017-12, Derivatives and Hedging (Topic 815)*, which reproduces Codification paragraph 815-20-25-43 (https://storage.fasb.org/ASU%202017-12.pdf, retrieved 2026-11-17, SHA-256 f2a20d94…8a2f). "Besides those hedged items and transactions that fail to meet the specified eligibility criteria, none of the following shall be designated as a hedged item or transaction in the respective hedges: … c. With respect to fair value hedges only: … 2. For a held-to-maturity debt security, the risk of changes in its fair value attributable to interest rate risk … d. With respect to cash flow hedges only: … 2. If variable cash flows of the forecasted transaction relate to a debt security that is classified as held-to-maturity under Topic 320, the risk of changes in its cash flows attributable to interest rate risk."
- **Still current as of June 2026:** KPMG, "FASB proposes targeted improvements to hedge accounting" (https://kpmg.com/us/en/frv/reference-library/2026/fasb-proposes-targeted-improvements-to-hedge-accounting.html, read 2026-11-17). It says FASB's proposed ASU of 17 June 2026 "would permit an entity to hedge the interest rate risk of HTM debt securities in both fair value and cash flow hedges", with comments due 17 August 2026.
- **Not confirmed:** whether that proposal has become final since August 2026. Searches found no final ASU, but fasb.org returned HTTP 403 to automated requests. The owner was asked to check.
- **Decision:** PLAN.md section 7's design stands. Hedges are sized against the AFS book only, because AFS losses reach AOCI and HTM interest-rate risk cannot currently be designated as a hedged risk. If the proposal becomes final, HTM hedging could be added as a separate, owner-approved change. LIMITATIONS.md records the pending proposal.

## D-046. Plan change: the ±200 bp full-hedge residual test

- **Date:** 2026-11-17, approved by the owner (option A)
- **Finding:** measured at ±25 bp, the AFS book's dollar convexity is +203,943 and the 5-year swap's is −124,762. The fully hedged book is therefore positively convex, predicting a residual of +15.8 at ±200 bp. At +200 bp the residual is +14.3, as predicted. At −200 bp it is −13.1: in a large rally the near-the-money AFS pools prepay, so the AFS book's duration shortens while the swap's does not, and the static hedge becomes too large. With mortgage pools removed from AFS, the residual is positive on both sides (+4.0, +2.6), which confirms the cause.
- **Change:** PLAN.md Phase 6 replaces "at ±200 bp the full hedge's residual has the sign implied by the AFS book's convexity" with three tests: (1) at +200 bp the residual has the sign of the hedged book's convexity; (2) at −200 bp it falls short of that convexity prediction because of prepayments, which is reported; (3) a control in which, with mortgage pools excluded from AFS, the residual at ±200 bp has the sign of the AFS book's convexity on both sides.
- **Alternative rejected:** (B) rebalancing hedges after large moves, a scope change because PLAN.md says hedges are never rebalanced.

## D-047. Hedging grid definitions

- **Phase:** 6
- **Decision:** `securities_delta_mv` is the whole portfolio's change in value (AFS + HTM). `net_delta_mv` adds the swap gain or loss. `aoci_net` is the AFS change plus the swap gain or loss. `loss_avoided` is the swap gain or loss. `carry_given_up` is minus the swaps' 12-month carry, with the floating rate taken from the scenario's curve. `net_carry` is the securities' carry plus the swap carry. A "No shock" row is shown in the CLI to give today's carry cost.
- **Why:** the plan's fields, with the one choice it leaves open (securities = whole book, not just AFS) made explicit. AOCI is the AFS-only view.

## D-048. Swap risk computed per $1M and scaled linearly

- **Phase:** 6
- **Decision:** each hedge tenor's DV01 and key-rate DV01s come from a $1M par swap through the same bump engine as the bonds, then scale with notional, because swap value is linear in notional. The key-rate system is solved with `numpy.linalg.solve`.
- **Measured:** bump-and-reprice swap DV01 matches the annuity formula within 1.2e-8 (2y), 5.0e-8 (5y) and 1.6e-7 (10y) relative, against a tolerance of 1e-6 fixed in advance.

## D-049. QuantLib swap benchmark

- **Phase:** 6
- **Decision:** `ql.VanillaSwap` with a semiannual fixed leg, a quarterly floating leg on a 3-month index projected off the same curve, 30/360 throughout, no calendar, zero fixing days, and the spread via `ZeroSpreadedTermStructure`. The floating leg is then worth exactly 1 − DF(T), as in Tenorwise. Tolerances: 1e-10 for rate and value.
- **Measured:** par rate within 1.6e-16 and values within 1.3e-15 on shocked curves (−200 to +200 bp) at spreads of 0 and 25 bp. Added to `docs/evidence/quantlib_report.json`.

## D-050. Contract additions (no field renamed or removed)

- **Phase:** 7
- **Decision:** PLAN.md section 8's field names are kept exactly. Added fields, each marked "added" in `tenorwise/snapshot/models.py`:
  - `data_date` in every file;
  - `id` and `name` on every sector and class row;
  - `stylized` and `proxy_for` on positions;
  - `stylized`, `stylized_note`, `pool`, `mortgage_rate`, `prepayment_model`, `comparison_treasury_bond` and `profile[].eff_convexity` in `mbs.json`;
  - `floor_bound` and `floored_tenor_years` on scenarios;
  - `base_market_value` in `scenarios.json`;
  - `swap_spread_bp`, `hedged_book`, `afs_dv01` and `strategies[].dv01_after` in `hedges.json`;
  - `quantlib_report_generated_at` in `evidence.json`.

  `scenarios.json` also gets a "base" (no shock) entry, and `hedges.json` its grid rows, so today's carry and hedge cost can be shown. Element shapes the plan left open: `shock_bp_by_tenor[]` is `{tenor_years, shock_bp}`; `fred_series[]` is `{id, title, use, observation_dates}`; `assumptions[]` is parsed from ASSUMPTIONS.md as `{id, text, where, effect, phase}`; `weight` is a percent of amortized cost.
- **Why:** ground rules and the plan require the stylized labels, the floor flag and the swap spread to be visible. The rest makes rows identifiable and the data date available everywhere. Reported to the owner, who is designing against the contract.

## D-051. Function-only `inputs.json` with full-precision engine inputs

- **Phase:** 7
- **Decision:** the build writes `inputs.json` to the function folder only, never to the web folder. It holds the par yields, the mortgage spread, the swap spread and the sized hedge swaps at full precision. `POST /api/scenario` rebuilds the market from it, so its answer equals the engine's exactly (tested).
- **Alternative rejected:** rebuilding from the rounded public files. The answer would drift from the engine by rounding.

## D-052. Deterministic serialization: 10 significant figures

- **Phase:** 7
- **Decision:** sorted keys, indent 1, every float rounded to 10 significant figures, negative zero normalized. `inputs.json` keeps full precision (still sorted and stable).

## D-053. Pinned fixture snapshot

- **Phase:** 7
- **Decision:** `data/fixtures/snapshot_v1/` is built from the pinned fixtures with `build_time` = the Treasury fixture's fetch time and `git_sha` = "fixture". Tests and evals use it. A test fails if a fresh fixture build differs from it by a single byte.

## D-054. One OpenAPI document; type generator run through npx with its own TypeScript 5

- **Phase:** 7
- **Decision:** `build_openapi()` merges the snapshot models into FastAPI's OpenAPI document (`docs/api/openapi.json`). `npm run gen:types` runs `npx -p typescript@5.9.3 -p openapi-typescript@7.13.0` to write `web/src/api/schema.d.ts`.
- **Why:** `openapi-typescript` 7.13.0, the latest release, declares a peer dependency on TypeScript ^5, while the app uses TypeScript 6.0.3 from the Vite template. Rejected: `--legacy-peer-deps`, which would silence the conflict inside the project.

## D-055. `/api/deploy-check` removed

- **Phase:** 7
- **Decision:** removed as planned in D-008. The import-isolation test now exercises `/api/health` and `/api/scenario` against the pinned snapshot. Phase 0's `tests/unit/test_build_snapshot.py` is superseded by `tests/unit/test_snapshot.py`.

## D-056. The next deploy needs `FRED_API_KEY` on Vercel

- **Phase:** 7
- **Decision:** `scripts/vercel_build.sh` runs the live snapshot build, which fails without `FRED_API_KEY` (by design: a failed build leaves the previous deployment live). Setting the variable on Vercel is an outward-facing action, so it will be done only after asking, at the next deploy.

## D-057. Verifier details within the plan's rule

- **Phase:** 8
- **Decision:** the rule and the 0.5% tolerance are exactly as in PLAN.md section 9. Details the plan leaves open:
  - % and bp convert (1 bp = 0.01%).
  - Money printed without "per bp" is accepted for a DV01 value. Money printed "per bp" is rejected for a plain dollar value.
  - Parentheses mean negative only for money, so "(as of 2026)" stays positive.
  - A dash between numbers is a range separator and the unit carries back ("2–5 years").
  - ISO dates must be context dates.
  - Markdown emphasis and list markers are removed before extraction.
  - Correct rounding accepts half-up or half-even.
  - Context numbers: tenors (1, 3, 6, 12 months; 1–30 years), shock sizes ±1/25/50/75/100/200/300 bp, hedge ratios 50%/100%, the data date, the replay dates and BNY's filing dates, plus every tool argument and every shock in a scenario the model looked up.

## D-058. Blocked responses withhold the failed tokens too

- **Phase:** 8
- **Decision:** in a `blocked` or `error` response, failed checks keep their tag and reason, but the token is replaced by "(withheld)". The reason quotes only the correct, verified display string.
- **Why:** "unverified text is never returned" (PLAN.md section 9). A failed token is unverified text. The test asserts the wrong figure appears nowhere in the response.

## D-059. Tool results carry display strings and IDs, never bare numbers

- **Phase:** 8
- **Decision:** every figure reaches the model as `{id, label, display}`. A test walks every tool result and fails on any JSON number. Large position lists show the main fields; filters show all fields.

## D-060. Rate limiting: per-IP first, Upstash REST, in-memory dev store refused on Vercel

- **Phase:** 8
- **Decision:** the per-IP count is checked first, and a request it rejects does not consume the global cap. Keys are `tw:ai:<UTC day>:ip:<sha256(salt:ip)[:32]>` and `tw:ai:<UTC day>:global`, expiring after two days. Missing configuration or an unreachable store means 503.
- **Local development:** `RATE_LIMIT_BACKEND=memory` uses an in-process counter. It is refused when `VERCEL` is set, so it cannot run in production.
- **Cap values (approved 2026-11-17):** `AI_LIMIT_PER_IP_PER_DAY=10`, `AI_LIMIT_GLOBAL_PER_DAY=150`. At an estimated worst case of about $0.07 per request on GLM-5.3, that bounds spend at roughly $10 a day; it will be revisited with Phase 9's measured cost per question. Set in Vercel at deploy; locally passed on the command line.

## D-061. Agent response additions

- **Phase:** 8
- **Decision:** the plan's fields are unchanged. Added: `notice` ("Draft, requires human review" on every commentary), `error`, `request_id`, `verification_rule` (the stated tolerance text, shown in the interface) and `usage.cost_is_upper_bound`. `values` includes the cited values and, for `derive` results, their inputs, so the provenance chain resolves.

## D-062. Dated LLM price list

- **Phase:** 8
- **Decision:** `data/llm/prices.json` holds Sail's list prices per model and tier as read on 2026-11-17. Cost per request is computed from reported token usage. Phase 9 re-reads the pricing page on the day the evals run, as PLAN.md requires.

## D-063. No real model has been called yet in Phase 8

- **Phase:** 8
- **Decision:** everything is tested with a scripted provider and, end to end, a local mock server. The live smoke test exists and is skipped by default. Running it waits for the owner's approval of the spend.

## D-064. Live smoke test findings and the truncated-tool-call fix

- **Date:** 2026-11-18 (UTC), owner-approved smoke test: one question and one commentary on `zai-org/GLM-5.3`
- **Question:** answered, 2 model calls, 5,129 prompt + 196 completion tokens, $0.0037 at list prices (cached tokens reported, so not an upper bound), 4.9 s, `asap` tier. All 12 numeric checks passed.
- **Commentary:** failed with HTTP 400 on the 4th model call, after 3 successful calls that ran 11 tools. Cost $0.0238 (17,262 + 5,199 tokens). The error body was not captured, because the provider error kept only the error code.
- **Most likely cause (not confirmed):** 5,199 completion tokens over 3 calls against a per-call cap of 4,096 suggests the submission was cut off (`finish_reason = length`). The loop then echoed the truncated, invalid-JSON tool arguments back in the history, which a provider can reject.
- **Fixes (all tested with a scripted provider):**
  - malformed tool arguments are never echoed back (`{}` is sent instead), and the model is told its output was cut off;
  - `finish_reason` is recorded;
  - commentary gets `max_completion_tokens` 8,192;
  - provider errors now carry the provider's code and the first 200 characters of its message, scrubbed of the key.
- **Next:** one more commentary run (about $0.03) to confirm, pending the owner's approval.
- **Rerun (owner-approved, 2026-11-18):**
  - The commentary succeeded on `zai-org/GLM-5.3`: 5 model calls running 13 tools, and all 67 numbers passed verification.
  - Usage: 34,435 prompt + 4,812 completion tokens, $0.0269 at list prices, 25.1 s.
  - The CLI output does not show `finish_reason` per call, so whether a cut-off happened and was handled is not known.
  - The HTTP 400 did not recur.

## D-065. Eval grading: engine gold, tagged values only

- **Phase:** 9
- **Decision:** each of the 36 questions has a gold function that runs the engine directly on the pinned market fixtures (`tenorwise/evals/engine.py`).
  - An answer is correct if its status matches and every gold value appears among the values tagged in the answer text, with the same unit and within the verifier's 0.5%.
  - Derived-value inputs that the response carries for provenance do not count.
  - A gold is sign-insensitive only where the question leaves the order of a difference open (D1, D5).
  - The analyst reads the pinned fixture snapshot, so runs are reproducible (PLAN.md section 8).
- **Why:** gold from the tools would grade the tools against themselves; counting untagged provenance values would credit numbers the answer never stated.
- **Alternatives rejected:** hand-typed expected numbers, which go stale; an LLM judge, which the plan rules out.
- **Measured exposure:** the coincidence test lists every tool value within 0.5% of a gold value: 17 in all, 6 equal by definition and 11 by coincidence. It is pinned so a new one is noticed (LIMITATIONS.md).

## D-066. Eval reporting and what goes into evidence.json

- **Phase:** 9
- **Decision:**
  - **Raw results:** JSON Lines in `docs/evidence/evals/raw/`, one line per run. `python -m tenorwise.evals report` writes `summary.json` and `report.md` from them.
  - **Per model:**
    - accuracy: mean over repeats, with the lowest and highest repeat;
    - block rate before repair: a repair was requested;
    - block rate after repair: status `blocked`;
    - verified-but-wrong: of the runs that passed verification (status `answered` or `cannot_answer`), the share graded wrong;
    - latency p50 and p95 on the eval machine;
    - mean cost per question.
  - **Per question and model:** the majority outcome over repeats, or "fail" with no majority.
  - **evidence.json:** carries only the contract fields (PLAN.md section 8):
    - `accuracy` is the mean, as a fraction from 0 to 1;
    - `block_rate` is after repair;
    - the ranges and the before-repair rate stay in the summary and report.
  - **Pinned test snapshot:** `--pin` builds it without eval results, so rerunning evals never changes it. Other builds publish `docs/evidence/evals/summary.json` if it exists.
- **Why:** the contract field names are fixed, so nothing was added to `evidence.json` without asking. Repairs are detected from the messages the eval sends, so the agent's response shape is unchanged.

## D-067. Running paid evals safely

- **Phase:** 9
- **Decision:** `python -m tenorwise.evals run --model … --max-cost …` refuses to start unless:
  - `data/llm/prices.json` was re-read today (PLAN.md section 10);
  - the model has a list price;
  - the credentials are set.

  Runs are sequential, so latency is not inflated by our own parallel requests. Each result is appended as it ends. No new question starts once the cost so far reaches `--max-cost`.
- **Prices:** re-read from https://docs.sailresearch.com/pricing.md on 2026-11-18. They were unchanged for the three eval models, so only `read_on` was updated.

## D-068. How the eval cost estimate is made

- **Phase:** 9
- **Decision:** `python -m tenorwise.evals estimate` replays the oracle (the shortest tool path per question) and counts the characters sent per model call.
  - **Tokens:** characters are converted with the tokens-per-character ratio from the measured smoke question (5,129 prompt tokens, GLM-5.3, D-064), replayed the same way.
  - **Assumptions:** 500 completion tokens per call (the smoke test measured 98), one extra call per question, and no cached-token discount.
  - **Result:** $1.49 for GLM-5.3, $0.14 for DeepSeek-V4.1-Flash and $3.17 for Kimi-K3.1-Pro, $4.80 in all for 3 repeats.
  - **Suggested budget per model:** twice the estimate.
- **Why:** an estimate from a measured call and the actual message sizes is more defensible than a guess. The budget guard bounds the error.

## D-069. Eval results, 2026-11-18

- **Phase:** 9
- **Runs:** owner-approved, with caps of $3.00 (GLM-5.3), $0.30 (DeepSeek-V4.1-Flash) and $6.40 (Kimi-K3.1-Pro).
  - 3 repeats of 36 questions each, run one model at a time, cheapest first. A systematic fault would have shown before the larger spend.
  - The raw files are in `docs/evidence/evals/raw/`; the summary and report are generated from them.
- **Results:** taken from `report.md`.
  - **Accuracy (mean):** Kimi-K3.1-Pro 100.0%, DeepSeek-V4.1-Flash 98.1%, GLM-5.3 97.2%.
  - **Failures:** all 5 were blocks of an untagged number that is not a context number. There were no errors and no verified-but-wrong answers.
- **Spend:** $1.04 measured, against the $4.80 estimate (D-068). The estimate's no-cache and 500-tokens-per-call assumptions were conservative.
- **Rate-limit caps (D-060):** the measured mean cost per question on GLM-5.3 is $0.0025, far below the $0.07 per-request worst case the caps were sized on. The caps are unchanged; changing them is the owner's call.
