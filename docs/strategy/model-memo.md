# Model recommendation memo

Which language model should run Tenorwise's analyst?

**Basis:** the eval run of 2026-11-18. Each model answered the 36 eval questions 3 times on Sail's asap tier, with prices read on 2026-11-18. A "task" here is one eval question: a rate-risk question that needs one to three tool calls.

**Source:** every figure below comes from `docs/evidence/evals/summary.json`, which is generated from the raw results by `python -m tenorwise.evals report`. A test checks that each number in this memo traces to those files.

## Results

| Model | Accuracy, mean (range over repeats) | Blocked before / after repair | Verified but wrong (95% upper bound) | Latency p50 / p95 | Cost per question |
|---|---|---|---|---|---|
| `moonshotai/Kimi-K3.1-Pro` | 100.0% (100.0% to 100.0%) | 5.56% / 0.0% | 0.0% (2.74%) | 10.0 s / 18.1 s | $0.0069 |
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | 98.1% (97.2% to 100.0%) | 24.1% / 1.85% | 0.0% (2.79%) | 12.6 s / 25.3 s | $0.000211 |
| `zai-org/GLM-5.3` | 97.2% (94.4% to 100.0%) | 17.6% / 2.78% | 0.0% (2.81%) | 4.7 s / 9.05 s | $0.00247 |

How to read the columns:

- **Blocked before repair:** the share of answers whose first draft failed the number check and went back to the model once.
- **Blocked after repair:** the share still failing after that single repair, which the user sees as "blocked", with a table of raw engine figures and no prose.
- **Verified but wrong:** answers that passed the number check but were still wrong.
- **Latency:** measured from the eval machine, not the deployed app.
- **Cost:** reported tokens at list prices. These are not upper bounds, because Sail reported cached tokens.
- **Precision:** some figures carry more digits than `report.md`. Every figure here is printed to a precision that passes the analyst's own verification rule against the summary.

## What the results say

- **No model gave a wrong answer that passed verification.** Every failure was a block, which is the safe way to fail. Even so, zero observed is not zero: with 105 to 108 verified answers per model, the rate could still be up to the upper bounds shown, for this question set only.
- **Kimi answered all 108 runs correctly.**
  - It needed a repair in 6 of 108 runs, the fewest of the models.
  - Its typical answer took 10.0 s, at $0.0069 per question.
- **GLM was the fastest:** 4.7 s for a typical answer and 9.05 s at p95.
  - It was blocked in 3 runs, all on derived-figure questions.
  - Its first-try failure rate was 17.6%.
- **DeepSeek was by far the cheapest,** at $0.000211 per question, but the slowest: 12.6 s typical and 25.3 s at p95.
  - Its first drafts failed the number check most often: 26 repairs in 108 runs.
  - Each repair costs an extra model call and time.
- **The accuracy differences are small.** Kimi's 108 passes against GLM's 105 is a difference of a few questions, which this sample cannot separate from chance. The repair rates differ more clearly (6, 19 and 26 repairs in 108 runs), and repairs cost latency every time they happen.

## Recommendation

Use `moonshotai/Kimi-K3.1-Pro` for the analyst.

**Why:**
- It had the best accuracy and the fewest repairs, and it was never blocked.
- In a product whose promise is that every number is checked, a blocked answer is safe but still a failed answer for the user.
- The analyst is interactive and low-volume, so its cost per question is small next to the value of a correct answer.

**Trade-off:**
- Kimi is slower than GLM: 10.0 s against 4.7 s typical, and 18.1 s against 9.05 s at p95.
- It also costs more per question: $0.0069 against $0.00247.
- If response time matters more than an occasional blocked answer, keep `zai-org/GLM-5.3`, the model configured today.
- `deepseek-ai/DeepSeek-V4.1-Flash-1017` suits offline batch work, where its price matters and its latency and repairs do not.

**Not covered by this memo:**
- **Commentary drafting.** It was not part of the eval and has been run live only on GLM (decision log D-064).
- **Reruns.** The eval should be rerun before any switch, and whenever Sail changes a model version or price.

The choice of model is the owner's. Switching means changing `LLM_MODEL` in the deployment's environment.

**Owner's decision (2026-11-18):** keep `zai-org/GLM-5.3` for now (decision log D-075). The analysis and recommendation above stand. The deployed analyst keeps the faster model and accepts its higher block rate.
