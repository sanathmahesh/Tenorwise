# Risks and controls

What could go wrong in Tenorwise, what catches it, and the evidence that the control works.

## Status and scope

**Tenorwise has not been validated. This document does not claim compliance** with SR 26-2 or any other guidance. SR 26-2 itself says it "does not set forth enforceable standards or prescriptive requirements".

The table uses the vocabulary of the US agencies' model risk guidance: Federal Reserve SR 26-2, issued with OCC Bulletin 2026-13 and FDIC FIL-15-2026 on 17 April 2026. Read on 18 November 2026. Tenorwise has three parts, and the guidance treats them differently:

- **The pricing engine is a model in the guidance's sense.**
  - The guidance defines a model as "a complex quantitative method, system, or approach that applies statistical, economic, or financial theories to process input data into quantitative estimates".
  - The engine fits that definition: it bootstraps a yield curve, discounts cash flows, models prepayments and revalues the book under rate shocks.
  - So its risks are described in the guidance's terms: conceptual soundness, outcomes analysis, ongoing model monitoring, model limitations, model inventory, effective challenge and model materiality.
- **The AI analyst is outside the guidance's scope.**
  - Footnote 3 says: "Generative AI and agentic AI models are novel and rapidly evolving. As such, they are not within the scope of this guidance."
  - The same footnote asks banks to apply their own risk management and governance practices to such tools.
  - So the analyst's controls are described as governance practices, with risk names from NIST AI 600-1 (the Generative AI Profile, July 2024), a non-supervisory reference.
- **Deterministic plumbing is not a model.**
  - The guidance's definition excludes "deterministic rule-based processes and software where there are no statistical, economic, or financial theories underpinning their design or use".
  - That covers the number verifier, the rate limiter and the data pipeline. They are controlled by ordinary software tests.

## How the engine stands against the guidance's terms

- **Model materiality** combines model purpose and model exposure.
  - In a bank, this engine's purpose would be managing financial risk exposures, which the guidance says is generally of greater risk.
  - Its exposure would be the size of the bond portfolio, so it would be material.
  - In this demonstration no real decision depends on it, so its exposure is nil.
- **Conceptual soundness:**
  - the design, assumptions and judgments are documented in `NOTES.md`, `ASSUMPTIONS.md` and the decision log;
  - the engine is benchmarked against an independent library, QuantLib, which the guidance names as a practical assessment ("benchmarking to other models").
- **Outcomes analysis has not been done.** Nothing compares the engine's estimates with real-world outcomes, for example predicted price changes with observed ones.
- **Ongoing model monitoring is partial.**
  - The build fails on stale or missing market data, and every change reruns the tests.
  - Nothing yet watches the engine's performance against market prices over time.
- **Effective challenge has not happened.** The guidance asks for critical analysis by objective experts with "sufficient independence". The builder and the owner are not independent, and a benchmark is evidence for a challenger, not a challenge.
- **Model limitations** are written in `LIMITATIONS.md` and shown where they matter. The mortgage model is labelled stylized in the code, the API and the interface.
- **Model inventory:** a draft entry is below.
- **Vendor and other third-party products:**
  - market data comes from FRED (Treasury yields from the H.15 release, and the Optimal Blue mortgage index);
  - the analyst's language models are hosted by a third party (Sail);
  - QuantLib is used only in tests.

### Draft model inventory entry

| Field | Entry |
|---|---|
| Name | Tenorwise rate-risk engine |
| Purpose | Estimate the value, rate sensitivity, scenario impact and hedge effects of a bond portfolio with AFS and HTM classes |
| Components | Treasury curve bootstrap; fixed-rate bond pricing and risk measures; stylized mortgage pass-through with an illustrative prepayment curve; scenario revaluation; pay-fixed swap hedges |
| Inputs | FRED Treasury par yields; FRED mortgage index; positions file |
| Outputs | Static snapshot files and the custom-scenario API |
| Users | Analysts (through the interface and the AI analyst) |
| Validation status | Not validated; no effective challenge; no outcomes analysis |
| Known limitations | `LIMITATIONS.md` |

## The pricing engine (a model under SR 26-2)

| Failure mode | Control | Evidence the control works | Guidance term |
|---|---|---|---|
| The yield curve is built wrong | Every input par bond must reprice to 100; the zero rates are benchmarked against QuantLib | `tests/unit/test_bootstrap.py::test_every_input_par_instrument_reprices_to_100`; `tests/benchmark/test_curve_quantlib.py::test_zero_rates_match_quantlib_on_the_fixture_curve` (11 curve points; the largest gap is in `docs/evidence/quantlib_report.json`) | Conceptual soundness (benchmarking) |
| A bond's price, duration or convexity is wrong | QuantLib benchmark; duration and convexity must predict a full reprice | `tests/benchmark/test_bond_quantlib.py::test_bond_measures_match_quantlib` (170 bonds); `tests/unit/test_bond_risk.py::test_duration_and_convexity_predict_a_100bp_reprice` | Conceptual soundness (benchmarking) |
| Swaps or hedge sizes are wrong | QuantLib benchmark for swap rates and shocked values; hedge DV01 checks | `tests/benchmark/test_swap_quantlib.py::test_par_rate_matches_quantlib` (6 swaps); `tests/benchmark/test_swap_quantlib.py::test_value_after_a_shock_matches_quantlib` (24 shocked values); `tests/unit/test_hedging.py::test_50pct_hedge_leaves_half_the_afs_dv01_and_the_full_hedge_about_none` | Conceptual soundness |
| HTM losses are reported as AOCI | AOCI is computed from AFS positions only | `tests/unit/test_scenarios.py::test_aoci_impact_equals_the_afs_change_and_excludes_htm` | Conceptual soundness |
| Stale or missing market data is silently filled | The build fails instead of filling gaps; the previous deployment stays live | `tests/unit/test_fred.py::test_stale_data_fails`; `tests/unit/test_fred.py::test_no_forward_fill_when_a_series_is_missing_on_every_recent_date`; `tests/unit/test_mortgage_spread.py::test_stale_mortgage_spread_fails` | Ongoing model monitoring; third-party data |
| The stylized prepayment model is read as a forecast | Labelled stylized in the code, the API and the interface | `tests/unit/test_mbs.py::test_model_is_labelled_stylized`; `tests/unit/test_snapshot.py::test_stylized_and_proxy_labels_reach_the_api` | Model limitations |
| A rate floor at zero distorts a falling-rate scenario | The floor is applied and flagged wherever it binds | `tests/unit/test_shocks.py::test_floor_at_zero_binds_and_is_flagged` | Model limitations |
| The engine is used beyond its purpose, for example for trading | The intended and out-of-scope uses are stated; the model card is completed in the final phase | Documentation only; no technical control | Model use |
| The engine drifts from reality over time | None yet | No outcomes analysis; listed as a gap | Outcomes analysis |

## The AI analyst (outside SR 26-2 by footnote 3: governance practices)

| Failure mode | Control | Evidence the control works | NIST AI 600-1 risk |
|---|---|---|---|
| The model states an invented or mis-copied number | Every number is checked against the engine's results. One repair is allowed; otherwise the answer is blocked with no prose and only a table of raw engine figures | `tests/agent/test_loop.py::test_still_wrong_after_repair_is_blocked_with_no_prose`; `tests/agent/test_verifier.py::test_property_canonical_displays_pass_and_last_digit_perturbations_fail`; eval: first drafts failed the check in 5.56% to 24.1% of runs depending on the model, and 0.0% to 2.78% remained blocked after repair | Confabulation (section 2.2) |
| The model does arithmetic itself | A `derive` tool computes sums, differences, ratios and percent changes; untagged numbers that are not context numbers fail | `tests/agent/test_loop.py::test_invented_untagged_numbers_are_blocked`; `tests/agent/test_tools.py::test_derive_computes_correctly`; eval: derived-figure accuracy 100.0% for two models and 83.3% for the third | Confabulation |
| A correct number appears in a wrong claim (the verifier cannot catch this) | Measured by evals; commentary always carries "Draft, requires human review"; the rollout plan's review step | `tests/agent/test_loop.py::test_commentary_is_verified_and_marked_for_review`; eval: verified-but-wrong 0.0% for every model, with one-sided 95% upper bounds of 2.74% to 2.81% on this question set | Confabulation; human-AI configuration (automation bias, section 2.7) |
| It answers forecasts, advice or questions outside the engine | Instructions to decline; tools return errors outside their range | `tests/agent/test_loop.py::test_cannot_answer`; eval: the decline group scored 100.0% for every model | Information integrity (section 2.8) |
| Truncated or malformed model output breaks the conversation | Malformed tool arguments are never sent back to the provider | `tests/agent/test_loop.py::test_malformed_tool_arguments_are_never_echoed_back` | Value chain and component integration (section 2.12) |
| The provider fails or changes behaviour | Retries only for refused-before-inference errors; a timeout and a cap on model calls; evals rerun before any model change | `tests/agent/test_provider.py::test_retries_refused_before_inference_errors_with_backoff`; `tests/agent/test_provider.py::test_timeout_is_an_error_and_not_retried`; `tests/agent/test_loop.py::test_call_cap` | Value chain and component integration |
| Abuse runs up cost | Per-IP and global daily caps in Redis; the AI endpoints refuse if Redis is down | `tests/api/test_agent_api.py::test_per_ip_daily_cap`; `tests/api/test_agent_api.py::test_global_daily_cap`; `tests/api/test_agent_api.py::test_refuses_when_redis_is_down_without_calling_the_model`; eval: cost per question from $0.000211 to $0.0069 | Information security (section 2.9) |
| Users' questions or addresses are exposed | No question text in logs; IP addresses stored only as salted hashes | `tests/api/test_agent_api.py::test_logs_have_request_metadata_but_never_the_question`; `tests/api/test_agent_api.py::test_ips_are_stored_only_as_salted_hashes` | Data privacy (section 2.4) |
| An API key leaks | Keys live only in environment variables; error messages are scrubbed; the web bundle is scanned for secrets | `tests/api/test_web_build.py::test_built_bundle_contains_no_key_or_key_like_variable`; `tests/agent/test_provider.py::test_errors_never_contain_the_key`; `tests/api/test_health.py::test_health_never_exposes_secrets` | Information security |
| The eval itself is wrong, so the evidence above is wrong | An oracle fake must score 36/36; the grader has its own case table; coincidental matches are pinned | `tests/evals/test_dry_run.py::test_oracle_scores_100_percent_and_report_is_consistent`; `tests/evals/test_questions_and_grader.py::test_grader_case_table`; `tests/evals/test_evidence_and_cli.py::test_gold_value_coincidences_across_all_tool_outputs_are_known` | Value chain and component integration |

## Residual risks

These remain after the controls above:

- **The engine:** no outcomes analysis, no effective challenge and no validation.
- **The AI analyst:**
  - a right number in a wrong claim is measured on 36 questions only, and real users' questions may be harder;
  - automation bias: readers may trust a verified-looking answer more than it deserves, and only human review addresses this.
- **Supply chain:** a build-time JavaScript dependency (picomatch, used by Vite) has a published denial-of-service advisory with no fixed release. It only processes the project's own file patterns at build time (decision log).

## Sources

- SR 26-2 attachment, *Supervisory Guidance on Model Risk Management*, 17 April 2026. https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf
- NIST AI 600-1, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, July 2024. https://doi.org/10.6028/NIST.AI.600-1
