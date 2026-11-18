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
- **Status:** to be confirmed by the Phase 0 preview deploy.

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
- **Note:** PLAN.md names 429 and 503 `model_capacity_unavailable`. Sail's `retries.md` (read 2026-11-17) also lists 503 `service_overloaded` as refused "before accepting a request". It was included in the probe and is raised with the owner for Phase 8.

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
