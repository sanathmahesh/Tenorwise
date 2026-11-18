# Notes

One section per phase. Each covers the finance concepts in plain English, how
the code implements them, why this design and what was rejected, what would
break it, and interview questions with short model answers.

## Sign conventions

To be written in Phase 1, when the first signed quantity (a rate shock) appears.
It will be stated once here and used everywhere.

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
