"""methods.json: every calculation a number can point back to.

Each method has a plain-English description, the formula, and a link into
NOTES.md. The AI analyst's ledger (Phase 8) cites these IDs.
"""

from __future__ import annotations

P1 = "NOTES.md#phase-1-yield-curve"
P2 = "NOTES.md#phase-2-bond-analytics"
P3 = "NOTES.md#phase-3-agency-mortgage-bonds-stylized"
P4 = "NOTES.md#phase-4-portfolio"
P5 = "NOTES.md#phase-5-scenarios"
P6 = "NOTES.md#phase-6-hedging"

METHODS: dict[str, dict[str, str]] = {
    "par_yield": {
        "name": "Treasury par yield",
        "plain_english": "The coupon at which a new Treasury of that maturity would sell for exactly 100, from FRED (H.15), on the market data date.",
        "formula": "FRED DGS1MO ... DGS30, latest date on which all 11 have values",
        "notes_anchor": P1,
    },
    "zero_rate": {
        "name": "Zero rate (bootstrap)",
        "plain_english": "The single rate for one date that discounts a dollar paid then back to today, solved maturity by maturity so every par bond prices to 100.",
        "formula": "T <= 0.5: z = ln(1 + yT)/T; T >= 1: solve (y/2) sum DF(t_i) + DF(T) = 1 with z linear in t between points",
        "notes_anchor": P1,
    },
    "discount_factor": {
        "name": "Discount factor",
        "plain_english": "What one dollar paid at a future date is worth today.",
        "formula": "DF(t) = exp(-z(t) t), z linear between curve points, flat beyond the ends",
        "notes_anchor": P1,
    },
    "rate_shock": {
        "name": "Rate shock",
        "plain_english": "Basis points added to each of the 11 par yields, then the curve is rebuilt. Key-rate shocks use tents at 2, 5, 10 and 30 years that sum to 1.",
        "formula": "y_i' = max(0, y_i + shock_i / 10000); rebuild",
        "notes_anchor": P1,
    },
    "bond_price": {
        "name": "Bond price",
        "plain_english": "Each remaining payment discounted at the zero rate plus the sector spread. Dirty includes accrued interest; clean does not.",
        "formula": "dirty = sum CF exp(-(z(t) + s) t); clean = dirty - accrued",
        "notes_anchor": P2,
    },
    "mod_duration": {
        "name": "Modified duration (yield-based)",
        "plain_english": "Roughly the % price change for a 1 percentage point move in the security's own yield.",
        "formula": "Macaulay / (1 + y/2), Macaulay = sum t PV / price",
        "notes_anchor": P2,
    },
    "eff_duration": {
        "name": "Effective duration (curve-based)",
        "plain_english": "Roughly the % value lost if all Treasury par yields rise 1 percentage point, from repricing at +/-25 bp.",
        "formula": "(P(-25bp) - P(+25bp)) / (2 P0 0.0025)",
        "notes_anchor": P2,
    },
    "eff_convexity": {
        "name": "Effective convexity",
        "plain_english": "How much duration itself changes as rates move. Negative means gains are capped in rallies (mortgage pools).",
        "formula": "(P(-25bp) + P(+25bp) - 2 P0) / (P0 0.0025^2)",
        "notes_anchor": P2,
    },
    "dv01": {
        "name": "DV01",
        "plain_english": "Dollars lost if all Treasury par yields rise 1 basis point. Positive for a long bond position; negative for a pay-fixed swap.",
        "formula": "(P(-1bp) - P(+1bp)) / 2",
        "notes_anchor": P2,
    },
    "key_rate_dv01": {
        "name": "Key-rate DV01",
        "plain_english": "DV01 from moving only the region of the curve around 2, 5, 10 or 30 years. The four add up to the total.",
        "formula": "(P(tent -1bp) - P(tent +1bp)) / 2",
        "notes_anchor": P2,
    },
    "mbs_cash_flows": {
        "name": "Mortgage pool cash flows (stylized)",
        "plain_english": "Monthly level payment plus prepayments driven by the refinancing incentive. Illustrative parameters, not calibrated.",
        "formula": "CPR = ramp (6% + 34% / (1 + exp(-3 (incentive - 1)))); SMM = 1 - (1 - CPR)^(1/12)",
        "notes_anchor": P3,
    },
    "mbs_price": {
        "name": "Mortgage pool price (stylized, static)",
        "plain_english": "Project the pool's cash flows once under the scenario's curve and discount them at the zero rate plus the agency mortgage spread.",
        "formula": "sum CF_m exp(-(z(t_m) + s) t_m), t_m = m/12",
        "notes_anchor": P3,
    },
    "avg_life": {
        "name": "Weighted average life",
        "plain_english": "On average, how many years until the principal comes back.",
        "formula": "sum t_m principal_m / sum principal_m",
        "notes_anchor": P3,
    },
    "mortgage_spread": {
        "name": "Mortgage spread",
        "plain_english": "Market mortgage rate (Optimal Blue index) minus the 10-year Treasury yield on the same date; held fixed in every scenario.",
        "formula": "OBMMIC30YF - DGS10",
        "notes_anchor": P3,
    },
    "amortized_cost": {
        "name": "Amortized cost",
        "plain_english": "The position's remaining cash flows discounted at the yield it was bought at (its book yield).",
        "formula": "sum CF (1 + book/2)^(-2t)",
        "notes_anchor": P4,
    },
    "unrealized": {
        "name": "Unrealized gain or loss",
        "plain_english": "Market value minus amortized cost.",
        "formula": "MV - amortized cost",
        "notes_anchor": P4,
    },
    "portfolio_aggregate": {
        "name": "Portfolio aggregation",
        "plain_english": "Values and DV01s add up; durations and convexities are market-value-weighted averages; weight is the share of amortized cost.",
        "formula": "sum; sum(MV_i D_i)/sum(MV_i); AC_group / AC_total",
        "notes_anchor": P4,
    },
    "scenario_change": {
        "name": "Scenario change in value",
        "plain_english": "Value on the shocked curve minus value today, with spreads held fixed.",
        "formula": "MV(shocked) - MV(base)",
        "notes_anchor": P5,
    },
    "aoci_impact": {
        "name": "AOCI impact",
        "plain_english": "The available-for-sale part of the change in value, which flows into equity. Pre-tax.",
        "formula": "sum over AFS positions of (MV(shocked) - MV(base))",
        "notes_anchor": P5,
    },
    "htm_unrecognized": {
        "name": "HTM change, not recognized",
        "plain_english": "The held-to-maturity part of the change in value: real, but not shown in the accounts.",
        "formula": "sum over HTM positions of (MV(shocked) - MV(base))",
        "notes_anchor": P5,
    },
    "carry_12m": {
        "name": "12-month carry",
        "plain_english": "Interest income over the next year at book yields; mortgage balances shrink with the scenario's prepayments. No funding cost or reinvestment.",
        "formula": "sum over 12 months of amortized cost x book yield / 12",
        "notes_anchor": P5,
    },
    "replay_2022": {
        "name": "2022 replay shock",
        "plain_english": "Each par yield's actual change from 31 Dec 2021 to 30 Dec 2022 (FRED), applied to today's curve.",
        "formula": "100 x (y(2022-12-30) - y(2021-12-31)) bp per tenor",
        "notes_anchor": P5,
    },
    "swap_par_rate": {
        "name": "Swap par rate",
        "plain_english": "The fixed rate that makes a new pay-fixed swap worth zero.",
        "formula": "K = (1 - DF(T)) / (0.5 sum DF(t_i)), swap curve = Treasury zero + spread",
        "notes_anchor": P6,
    },
    "swap_value": {
        "name": "Swap value (pay fixed)",
        "plain_english": "Value of receiving floating and paying the fixed rate; gains when rates rise.",
        "formula": "N ((1 - DF(T)) - K 0.5 sum DF(t_i))",
        "notes_anchor": P6,
    },
    "hedge_sizing": {
        "name": "Hedge sizing",
        "plain_english": "DV01 hedges size one 5-year swap to offset 50% or 100% of the AFS DV01; the key-rate hedge solves 2/5/10-year swaps to zero the 2y, 5y and 10y+30y buckets.",
        "formula": "N = -share x DV01_AFS / DV01_swap; key-rate: A n = -b",
        "notes_anchor": P6,
    },
    "aoci_net": {
        "name": "AOCI net of hedges",
        "plain_english": "AFS change plus the swaps' gain or loss, treating swaps as perfectly effective fair-value hedges.",
        "formula": "AFS change + swap P&L",
        "notes_anchor": P6,
    },
    "carry_given_up": {
        "name": "Carry given up",
        "plain_english": "What the hedge costs in a year: fixed rate paid minus the 3-month floating rate received, on the notional.",
        "formula": "-N (float_3m - K)",
        "notes_anchor": P6,
    },
}
