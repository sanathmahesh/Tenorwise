Read PLAN.md and its progress log (section 17) before doing anything.

# Ground rules (copied from PLAN.md section 3)

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
