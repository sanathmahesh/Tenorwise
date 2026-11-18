# Rollout plan

How a bank could pilot Tenorwise's analyst with its investment portfolio team.

**This is a proposal. It has not been executed.** No bank, team or user has piloted Tenorwise. Every threshold below is a proposed starting point for the pilot's owners to set, not a measured result.

## Scope of the pilot

**In scope:**
- internal analysis on the bank's investment securities portfolio;
- answering rate-risk questions;
- drafting commentary for the investment or asset-liability committee.

**Out of scope:** trading decisions, external reporting, anything sent to customers, and any lending decision.

## Before the pilot starts

- **The engine:**
  - is entered in the bank's model inventory;
  - goes through the bank's model validation, including effective challenge by independent reviewers.

  If the pilot must start first, SR 26-2 describes the alternative: inform users of the model's limitations and place limits on its use. Here, the pilot's scope is that limit.
- **The data:** the bank's own positions and market data replace the model book and FRED feeds, and the engine is re-benchmarked on them.
- **The AI provider:** it passes the bank's third-party risk management. No customer or personal data goes to the provider; questions about the bank's own book are the only input.
- **The model:** the eval is rerun on the bank's data with the chosen model (see the model recommendation memo), and the results are kept as the pilot's baseline.

## Pilot group

- Three to five analysts and one portfolio manager from the investment portfolio team, for six weeks.
- A named reviewer from the team signs off every commentary draft.
- A model risk contact receives the weekly report.

## Human review

**Commentary drafts:**
- Every draft is labelled "Draft, requires human review" (as the app already does).
- A named reviewer signs it off before it leaves the team.
- For each number, the reviewer opens its provenance link and checks the sentence around it. The verifier proves the number came from the engine, not that the claim is right.

**Answers to questions** are for exploration. Any figure copied into a document is checked through its provenance link first.

**Weekly sample review:** the reviewer grades a sample of the week's answers as right or wrong. This measures the verified-but-wrong rate in real use, which the eval can only estimate.

## What is logged

**For every request:**
- request ID and time;
- a pseudonymous user ID;
- model, tier, tokens, cost and latency;
- tools called;
- verification outcome, repair used or not, blocked or not;
- the snapshot's market data date and build.

The public demo already logs the same metadata, without question text (`tests/api/test_agent_api.py::test_logs_have_request_metadata_but_never_the_question`).

**For the pilot only, with users told in advance:** the question and answer text, kept for 90 days for the weekly review and deleted afterwards.

**Reviewer sign-offs and corrections,** so that repeated errors can be traced to a question type, a tool or the prompt.

## Rollback triggers

| Trigger | Action |
|---|---|
| A displayed number does not trace to the engine (this should be impossible; it means a verifier fault) | Turn the AI endpoints off at once and investigate |
| A verified-but-wrong answer reached a document outside the team | Pause commentary drafting; review the case and the controls |
| The weekly sample's verified-but-wrong rate is above the eval's upper bound for two weeks in a row | Revert to the previous model or prompt and rerun the eval |
| The block rate after repair is more than double the eval baseline for a week | Check for a provider or model change; revert the model if confirmed |
| The provider changes the model version or terms, or cost exceeds the pilot budget | Pause, rerun the eval, and decide before resuming |
| Market data is stale | Already handled: the build fails and the previous snapshot stays live |

**Kill switch:**
- **How:** set the global daily cap to zero (`AI_LIMIT_GLOBAL_PER_DAY=0`).
- **Effect:** every AI request is refused before the model is called, while the engine's pages keep working (`tests/api/test_agent_api.py::test_a_global_cap_of_zero_turns_the_ai_endpoints_off_and_leaves_the_rest_working`).
- **On Vercel:** the change applies after a redeploy.
- **Reverting the model:** change `LLM_MODEL` back.

## After the pilot

Widening use is the bank's decision. It would rest on three things:
- the weekly review results;
- the reviewers' view of time saved, measured the way the effort page measures it;
- no rollback trigger in the final two weeks.
