# Deploying Tenorwise

One Vercel project serves everything:
- the static site (`web/dist`);
- the snapshot files the site reads;
- one Python function (`api/index.py`) for `/api/*`.

Vercel runs `scripts/vercel_build.sh` at each deploy. It builds the snapshot from live FRED data and publishes the eval results into `evidence.json`. If FRED fails or its data is stale, the build fails and the previous deployment stays live.

Every deploy, the database creation and any paid smoke test need the owner's approval first (PLAN.md ground rule 10).

## 1. Create the Upstash Redis database (owner)

The daily caps on the AI endpoints live in Redis. Without it, the AI endpoints refuse to run, and the rest of the site works as normal.

1. At https://console.upstash.com, create a **new** Redis database just for Tenorwise; it shares nothing with any other project.
   - Choose a region near the Vercel function. Vercel's default function region is Washington, D.C. (`iad1`); check Project Settings → Functions.
   - The free plan is enough. The site makes at most two Redis calls per AI request.
2. From the database's REST API section, copy the REST URL and the REST token into the Vercel variables below. Never paste them into a chat.

## 2. Set the environment variables in Vercel (owner)

Set these under Project Settings → Environment Variables, for Production. Add them to Preview as well if previews should run the AI analyst.

| Variable | Value | Used by |
|---|---|---|
| `FRED_API_KEY` | your FRED API key | build (snapshot) |
| `LLM_BASE_URL` | `https://api.sailresearch.com/v1` | function |
| `LLM_API_KEY` | your Sail API key | function |
| `LLM_MODEL` | `zai-org/GLM-5.3` (the owner's choice, D-075) | build (`meta.json`) and function |
| `UPSTASH_REDIS_REST_URL` | from step 1 | function |
| `UPSTASH_REDIS_REST_TOKEN` | from step 1 | function |
| `IP_HASH_SALT` | a long random value, for example the output of `openssl rand -hex 32` | function |
| `AI_LIMIT_PER_IP_PER_DAY` | `10` (approved, D-060) | function |
| `AI_LIMIT_GLOBAL_PER_DAY` | `150` (approved, D-060) | function |

Do not set `RATE_LIMIT_BACKEND` on Vercel. It is for local development, and the function refuses it.

## 3. Add the firewall rate-limit rule (owner)

This rule stops bursts. The daily caps in Redis bound the total. The Hobby plan allows one rule per project, keyed by IP, with a fixed window of 10 seconds to 10 minutes.

1. In the Vercel dashboard, open the project, then Firewall in the sidebar.
2. Select Configure (top right), then + New Rule.
3. Fill in the rule:
   - **Name:** `AI analyst burst limit`.
   - **If:** Request Path, with the operator that matches a prefix (such as Starts with), value `/api/agent`.
   - **Then:** Rate Limit, Fixed Window, Time Window `60s`, Request Limit `5`, key IP, action Too Many Requests (429).
4. Save the rule, select Review Changes, then Publish.

To watch the rule's effect before it blocks anything, set the action to Log first.

## 4. Deploy (after approval)

```bash
npx vercel@65.12.1 deploy --prod --build-env TENORWISE_GIT_SHA=$(git rev-parse --short HEAD)
```

## 5. Smoke test the live site (paid, after approval)

The script checks:
- the health endpoint;
- that the site serves the app;
- that the static data date matches the API's and is at most 7 days old;
- that one AI question comes back answered with every number verified;
- that a 429 arrives once the per-IP daily cap is passed.

```bash
uv run python scripts/smoke_live.py https://tenorwise.vercel.app --pace 15
```

Points to know before running it:
- **It uses the cap.** It sends up to the per-IP cap of AI requests. Most of them are a question the analyst declines, which costs one cheap model call each.
- **It blocks your own address for the day.** Afterwards your IP cannot use the analyst until the next UTC day.
- **`--pace 15`** spaces the requests so the firewall rule is not what answers with the 429. The script reports which limit sent the 429, and only the app's per-IP cap passes.
