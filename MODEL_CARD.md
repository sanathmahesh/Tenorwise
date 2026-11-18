# Model card

Tenorwise is a public demonstration of interest-rate risk analysis on a model bank bond portfolio, with an AI analyst whose numbers are checked against the pricing engine. It has not been validated. It is not investment advice. Every measured figure below is also in [RESULTS.md](RESULTS.md), which is generated from the evidence files.

## Intended use

- **Exploring rate risk:** how a bank-style bond portfolio responds to rate scenarios.
  - the change in market value;
  - how much of it reaches AOCI (available-for-sale) and how much is held-to-maturity and not recognized;
  - the trade-off between loss avoided and carry given up for four swap hedges.
- **The AI analyst:** asking it questions in plain English, and drafting a portfolio commentary for a person to review.
- **Showing a method:** how a language model can be used in an asset-side workflow without producing a number itself.

Users are learners, interviewers and analysts studying the concepts. The data is public: FRED Treasury yields, the Optimal Blue mortgage index via FRED, and a portfolio mix based on BNY's Form 10-Q.

## Out-of-scope use

- Trading, hedging, accounting or capital decisions for any real portfolio.
- Statements about any bank's actual holdings. The positions are design choices sized from a public filing's mix.
- Forecasts of rates or prices, and investment advice. The analyst is instructed to decline both.
- Regulatory or financial reporting, and anything customer-facing.
- Using the mortgage pool's prepayment model as a forecast. It is stylized and illustrative.
- Questions about securities that are not in the model book, or shocks outside the engine's range.

## Components

- **Market data:** FRED Treasury par yields (H.15 release) and the mortgage index, fetched at each deploy. The build fails rather than fill a gap or use stale data.
- **Pricing engine:** deterministic Python.
  - It covers the Treasury curve bootstrap, fixed-rate bond pricing and risk measures, a stylized agency mortgage pass-through, scenario revaluation and pay-fixed swap hedges.
  - It is a model in the sense of SR 26-2: it applies financial theory to input data to produce estimates.
- **AI analyst:** a tool-calling language model, served by Sail.
  - The production model is `zai-org/GLM-5.3`, set by `LLM_MODEL`.
  - Its tools read the engine's outputs, and a `derive` tool does any arithmetic, so the model never calculates.
  - It is outside SR 26-2 by footnote 3, so its controls are governance practices.
- **Verifier:** deterministic code that checks every number in the analyst's text before anything is shown. It allows one repair; if that fails, the answer is blocked with no prose.
- **Controls on the AI endpoints:**
  - at most 6 model calls per request;
  - questions of up to 1,000 characters;
  - per-IP and global daily caps, kept in Redis under salted IP hashes;
  - logs that record metadata only, never question text.
- **Interface:** a static site that renders the snapshot files, plus a Python function for custom scenarios and the analyst.

## Assumptions

Every simplifying assumption is listed in [ASSUMPTIONS.md](ASSUMPTIONS.md) and on the About page. Those with the largest effect on results:

- the stylized prepayment curve (A-15);
- static valuation with no rate volatility (A-17);
- sector spreads that do not move (A-25);
- instantaneous shocks (A-27);
- a swap curve equal to the Treasury curve plus a flat spread, currently zero (A-32);
- perfectly effective hedges (A-34) that are never rebalanced (A-35).

## Limitations

The full list is in [LIMITATIONS.md](LIMITATIONS.md). The most important:

- Verification proves each number came from the engine and was copied correctly, not that the sentence around it is right.
- The engine has had no validation, no effective challenge and no outcomes analysis against real market moves.
- The mortgage pool is stylized and the IG corporates are a proxy.
- The evals cover 36 questions written by the builder.
- Latency was measured on the eval machine, not in the deployed app.
- The interface was tested in Chromium only.

## Validation evidence

This is evidence, not a validation.

- **Benchmark against QuantLib (2026-11-18):**
  - The engine agreed with QuantLib, an independent library, on the pinned curve for 2026-11-16.
  - Coverage: 11 curve points, 170 bonds, 6 swap rates and 24 shocked swap values.
  - The largest difference per measure is in [RESULTS.md](RESULTS.md).
- **Tests:** unit, property and benchmark tests run on every change. [docs/strategy/risk-controls.md](docs/strategy/risk-controls.md) names the test behind each control.
- **Evals (2026-11-18):** 36 questions, 3 repeats per model, graded against figures computed by the engine.
  - Accuracy: 97.2% for `zai-org/GLM-5.3` (production), 98.1% for `deepseek-ai/DeepSeek-V4.1-Flash-1017` and 100.0% for `moonshotai/Kimi-K3.1-Pro`.
  - Blocked after repair: 0.0% to 2.78%.
  - Verified but wrong: none observed, with a one-sided 95% upper bound of 2.74% to 2.81% on this question set.
- **Not done:** outcomes analysis against real market outcomes, and an independent review.

## Verification tolerance

Every number in an answer is checked against the engine before it is shown. A tagged number must equal the cited value's display string, or be that value correctly rounded to the printed precision and within 0.5% of it; an explicit sign must match. An untagged number must be a context number (a tool argument, tenor, shock size, hedge ratio, horizon or date). One failure blocks the answer.

Implemented in `tenorwise/agent/verifier.py`; the same text is returned with every AI answer (`verification_rule`) and shown in the interface. Verification proves each number came from the engine and was copied correctly, not that the sentence around it is right.

## Human review procedure

In this public demonstration no reviewer is assigned. This is the procedure a team would follow, also set out in the [rollout plan](docs/strategy/rollout-plan.md), which has not been executed.

- **Commentary drafts:** every draft carries "Draft, requires human review". Before it leaves the team, a named reviewer:
  1. opens the provenance link of every number and checks that the sentence around it is right;
  2. checks that the stylized and proxy caveats are present and the market data date is current;
  3. edits the text as needed and signs it off with their name and the date, recorded with the request ID.
- **Answers to questions** are for exploration. A figure copied into any document is re-checked through its provenance link first.
- **Blocked answers:** use the engine's own table of figures. Never rewrite the withheld text from memory.
- **Weekly review:** a reviewer grades a sample of answers, to measure in real use the verified-but-wrong rate the evals can only estimate.
