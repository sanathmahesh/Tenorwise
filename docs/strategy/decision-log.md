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

