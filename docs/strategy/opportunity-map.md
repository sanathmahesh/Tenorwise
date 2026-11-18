# Opportunity map

Where could AI help a bank's investment and lending teams, and why did Tenorwise pick rate-risk analysis of the bond portfolio?

The scores below are reasoned judgments from public sources, not measurements or practitioner interviews. The owner reviewed them on 2026-11-18 and asked for no changes. The sources are listed at the end.

## Rubric

Each workflow gets three scores from 1 to 5.

- **Value: how much a recurring decision improves, or how much time it saves.** This depends on how often the work happens and how much money rides on it.
  - 5: a core, recurring decision on a large book.
  - 3: a useful time saving on routine work.
  - 1: rare or low stakes.
- **Feasibility: can a small team build it now, and can its output be checked?** This depends on access to data, a source of truth to check answers against, and whether an eval can be written.
  - 5: public data, a deterministic engine, and every output checkable.
  - 1: needs proprietary data and has no ground truth.
- **Risk: the harm if the AI is wrong, and how hard that is to catch. Higher is riskier.** This depends on who sees the output (an internal analyst, or a customer, regulator or the public), the legal or regulatory exposure, and whether a mistake can be reversed.
  - 5: customer-facing or public output that is legally required to be accurate.
  - 1: internal, reviewed and easy to reverse.

**Decision rule:** prefer high value and high feasibility, where deterministic checks plus human review can contain the risk. A risk score of 5 rules a workflow out as a first project, whatever its value.

## Scores

| # | Workflow | Team | Value | Feasibility | Risk |
|---|---|---|---|---|---|
| 1 | Rate-risk scenario analysis and commentary | Investment portfolio | 4 | 5 | 2 |
| 2 | Hedge accounting documentation drafts | Treasury and investment portfolio | 3 | 2 | 4 |
| 3 | Research summaries for securities purchases | Investment portfolio | 3 | 4 | 2 |
| 4 | Prepayment model monitoring commentary | Investment portfolio and model risk | 3 | 2 | 3 |
| 5 | Investment securities disclosure drafts | Finance (external reporting) | 2 | 3 | 5 |
| 6 | Commercial credit memo first drafts | Commercial lending | 4 | 3 | 3 |
| 7 | Credit agreement and covenant extraction | Commercial lending operations | 4 | 4 | 3 |
| 8 | Covenant compliance checks | Commercial lending and credit risk | 3 | 3 | 3 |
| 9 | Early-warning signals from news and filings | Credit risk | 3 | 3 | 3 |
| 10 | Adverse action reasons for consumer credit | Consumer lending | 3 | 2 | 5 |

## Workflows

### 1. Rate-risk scenario analysis and commentary

Answering "if rates move, what happens to the bond portfolio, to AOCI, and to the hedges?", and drafting the commentary for the investment or asset-liability committee.

- **Value 4.** This analysis is recurring and sits on a large book. The split between available-for-sale securities (AFS, whose value changes flow into AOCI and so into equity) and held-to-maturity securities (HTM, whose value changes are not recognized) is reported in banks' filings, for example BNY's 10-Q, Note 2. It is not a 5 because the decision itself (whether to hedge, and how much) stays with people.
- **Feasibility 5.** Everything is public: Treasury yields from FRED and the portfolio mix from a 10-Q. A deterministic engine computes every figure, so each number an AI states can be checked automatically, and an eval can grade answers without a human. Tenorwise built and measured this end to end.
- **Risk 2.** The audience is internal analysts, and drafts are reviewed before they leave the team. The pricing engine is a "model" in SR 26-2's sense, because it applies financial theory to input data to produce estimates, so the bank's existing model risk management covers it. The AI layer is outside SR 26-2 (footnote 3) and needs its own governance controls. The main residual risk is a correct number placed in a wrong sentence.

### 2. Hedge accounting documentation drafts

Drafting the documentation a bank prepares when it designates a swap as a hedge.

- **Value 3.** The documents are detailed but follow templates, and there are few designations. The time saved per document is real, but the volume is low.
- **Feasibility 2.** It needs the bank's hedge accounting policy, its templates and its effectiveness test results. No public source of truth exists to check a draft against.
- **Risk 4.** Mistakes flow into the financial statements. Accounting and the auditors would have to check every line, which eats most of the time saved.

### 3. Research summaries for securities purchases

A first-pass summary of offering documents and disclosures before the investment team buys a security.

- **Value 3.** It speeds up reading. The purchase decision still rests on the analyst's own analysis, not on the summary.
- **Feasibility 4.** Many offering documents are public. Every extracted fact can be checked by quoting the source passage, so an eval can grade it.
- **Risk 2.** The output is internal and read by the analyst who makes the decision. A wrong fact can be caught by checking its quote.

### 4. Prepayment model monitoring commentary

Explaining why mortgage bonds' actual prepayment speeds differ from what the bank's model predicted.

- **Value 3.** SR 26-2 expects ongoing model monitoring, and this explanation work recurs every month.
- **Feasibility 2.** It needs pool-level actual prepayment data and the bank's own model outputs, mostly licensed data. Tenorwise's prepayment model is stylized, so this could not be tested here.
- **Risk 3.** The commentary feeds decisions about model overlays and recalibration. A wrong explanation could delay a needed fix. Model owners and validators review it.

### 5. Investment securities disclosure drafts

Drafting the narrative of the investment securities note in quarterly filings.

- **Value 2.** It is quarterly work for a small team, and much of the text carries over from quarter to quarter.
- **Feasibility 3.** Numbers could be verified the way Tenorwise verifies its own, but the source tables live in internal systems.
- **Risk 5.** This is public financial reporting, and an error is a misstatement that investors and regulators rely on. It is ruled out as a first project.

### 6. Commercial credit memo first drafts

A first draft of the memo that goes to a credit officer for each new loan or renewal: the borrower's financials, the structure and the risks.

- **Value 4.** Memos are frequent and slow to write, so a first draft saves analyst time on a high-volume task.
- **Feasibility 3.** It needs internal borrower data, such as financial statement spreads and the relationship history. The numbers could be verified against the spread, as Tenorwise does against its engine.
- **Risk 3.** The credit decision stays with credit officers, but a memo shapes it, and a wrong borrower figure could mislead an approval. Every draft would need human review.

### 7. Credit agreement and covenant extraction

Pulling covenant terms, defined terms and reporting dates out of long credit agreements into the bank's systems.

- **Value 4.** The work is manual, recurring and slow, and the extracted terms drive monitoring for the life of the loan.
- **Feasibility 4.** The documents are already in hand. Each extracted term can be checked against the quoted clause, and the output is structured, so an eval can grade it.
- **Risk 3.** A missed or wrong covenant term weakens monitoring. Quoting the source clause and reviewing the extraction contain this.

### 8. Covenant compliance checks

Computing each borrower's covenant ratios from its financial statements and flagging breaches.

- **Value 3.** The checks are periodic for every borrower, and much of the work is already in spreadsheets.
- **Feasibility 3.** The arithmetic belongs in deterministic code, as in Tenorwise. However, each agreement defines its own terms (for example, what counts as EBITDA), so those definitions must be extracted first (workflow 7).
- **Risk 3.** A missed breach delays action on a weakening borrower, and a false breach wastes relationship time.

### 9. Early-warning signals from news and filings

Watching borrowers' news and filings for signs of trouble, and sending the relevant items to credit risk.

- **Value 3.** The monitoring is broad and repetitive, so triage helps.
- **Feasibility 3.** News and filings are public. Whether a signal was right is only known later, which makes evals slower and harder to build.
- **Risk 3.** False alarms waste time and missed signals delay action. People still triage every alert.

### 10. Adverse action reasons for consumer credit

Producing the specific reasons given to consumers whose credit applications are declined.

- **Value 3.** The volume is high, and every declined applicant must get specific reasons.
- **Feasibility 2.** It needs the credit decision model and applicant data. Whether a stated reason is accurate is hard to verify.
- **Risk 5.** The output is customer-facing and legally required. The Equal Credit Opportunity Act and Regulation B require specific and accurate reasons for adverse action, and the CFPB has said complex algorithms do not change that (Circular 2022-03). There is also fair-lending exposure. It is ruled out as a first project.

## Why this use case

Tenorwise takes workflow 1, for five reasons:

- **It is the most feasible.** It uses only public data (FRED yields and a portfolio mix based on BNY's 10-Q), so it can be built and shown publicly without customer data or personal information.
- **The main AI risk can be checked by code.** Generative models state wrong numbers confidently, which NIST AI 600-1 calls confabulation (section 2.2). Here a deterministic engine is the source of truth for every figure, so code can check each number before it is shown, and evals can measure what slips through.
- **It has a clean governance story.** The engine is a model under SR 26-2's definition and the AI layer is outside it (footnote 3). The project shows how each would be governed.
- **It matters.** Interest-rate risk in bond portfolios, and its effect on AOCI, is a central topic for a bank's asset side.
- **What it gives up.** It is internal analysis, not a revenue workflow, and the time it saves has not been measured: the effort study was designed but not run (D-081).

**Next candidates:**

- **Workflow 7 (covenant extraction) and workflow 3 (research summaries)** have high feasibility, and their outputs can be checked by quoting the source.
- **Workflow 6 (credit memos)** has high value but needs internal borrower data.

## Sources

- Board of Governors of the Federal Reserve System, FDIC and OCC, *Supervisory Guidance on Model Risk Management*, SR 26-2 attachment, 17 April 2026: the definition of a model, materiality, and footnote 3 on generative and agentic AI. https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf
- NIST AI 600-1, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, July 2024: confabulation (section 2.2) and human-AI configuration, including automation bias (section 2.7). https://doi.org/10.6028/NIST.AI.600-1
- Consumer Financial Protection Bureau, Circular 2022-03, *Adverse action notification requirements in connection with credit decisions based on complex algorithms*, 26 May 2022. The page was read on 18 November 2026 and showed no withdrawal notice. https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/
- The Bank of New York Mellon Corporation, Form 10-Q for the quarter ended 30 September 2026, Note 2, Investment securities (cited in `data/sources/`).
- FRED, Federal Reserve Bank of St. Louis: Treasury par yields from the H.15 release.
