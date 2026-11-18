"""The 36 eval questions, six per group (PLAN.md section 10).

Each question has:
  - a gold function that runs the engine directly (evals/engine.py), never the
    agent's tools, and returns the values a correct answer must cite, with units;
  - a reference plan: the tool calls an ideal analyst would make and the values
    it would cite. The plan is used only by the oracle fake in the dry run, to
    prove every question is answerable through the tools; real models never see it.

Question IDs: A lookups, B single scenarios, C hedges, D derived figures,
E mortgage behaviour, F questions the analyst should decline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tenorwise.evals.engine import PCT, USD, EngineContext
from tenorwise.evals.grader import Gold

CATEGORIES = ("lookup", "scenario", "hedge", "derived", "mortgage", "decline")
CATEGORY_NAMES = {
    "lookup": "Curve and portfolio lookups",
    "scenario": "Single-scenario results",
    "hedge": "Hedge comparisons",
    "derived": "Derived figures (need the derive tool)",
    "mortgage": "Mortgage behaviour (stylized pool)",
    "decline": "Should decline",
}

Ref = tuple[int, str]  # (index of the plan step that returned the value, its label)


@dataclass(frozen=True)
class Call:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Derive:
    operation: str
    operands: tuple[Ref, ...]
    label: str


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str
    gold: Callable[[EngineContext], list[Gold]]
    plan: tuple[Call | Derive, ...] = ()
    cite: tuple[Ref, ...] = ()

    @property
    def expected_status(self) -> str:
        return "cannot_answer" if self.category == "decline" else "answered"


def _none(e: EngineContext) -> list[Gold]:
    return []


def _pct_change(a: float, b: float) -> float:
    return 100.0 * (b - a) / abs(a)


QUESTIONS: list[Question] = [
    # ------------------------------------------------------------------ A. lookups
    Question(
        "A1", "lookup", "What is the 10-year Treasury par yield on the market data date?",
        lambda e: [Gold(PCT * e.par_yield(120), "pct", "10-year par yield")],
        (Call("get_curve"),), ((0, "10Y Treasury par yield"),),
    ),
    Question(
        "A2", "lookup", "What is the total market value of the portfolio?",
        lambda e: [Gold(USD * e.pv.summary.market_value, "usd", "portfolio market value")],
        (Call("get_portfolio_summary"),), ((0, "Portfolio market value"),),
    ),
    Question(
        "A3", "lookup", "What is the portfolio's DV01?",
        lambda e: [Gold(USD * e.pv.summary.dv01, "usd_per_bp", "portfolio DV01")],
        (Call("get_portfolio_summary"),), ((0, "Portfolio DV01"),),
    ),
    Question(
        "A4", "lookup", "What is the effective duration of the held-to-maturity book?",
        lambda e: [Gold(e.pv.by_class["HTM"].eff_duration, "years", "HTM effective duration")],
        (Call("get_portfolio_summary", {"group": "class"}),), ((0, "Held-to-maturity effective duration"),),
    ),
    Question(
        "A5", "lookup", "How large is the unrealized gain or loss on the agency mortgage bonds?",
        lambda e: [Gold(USD * e.pv.by_sector["agency_mbs"].unrealized, "usd", "agency MBS unrealized")],
        (Call("get_portfolio_summary", {"group": "sector"}),), ((0, "Agency mortgage bonds unrealized gain or loss"),),
    ),
    Question(
        "A6", "lookup", "What are the market value and the DV01 of position UST-A3?",
        lambda e: [
            Gold(USD * e.position("UST-A3").market_value, "usd", "UST-A3 market value"),
            Gold(USD * e.position("UST-A3").dv01, "usd_per_bp", "UST-A3 DV01"),
        ],
        (Call("get_positions", {"position_id": "UST-A3"}),), ((0, "UST-A3 market value"), (0, "UST-A3 DV01")),
    ),
    # ------------------------------------------------------------------ B. single scenarios
    Question(
        "B1", "scenario", "If every Treasury yield rises 100 bp at once, how much does the portfolio's market value change?",
        lambda e: [Gold(USD * e.scenarios["parallel_up_100"].total.delta_mv, "usd", "+100 bp change in value")],
        (Call("run_scenario", {"scenario_id": "parallel_up_100"}),), ((0, "Change in market value, total"),),
    ),
    Question(
        "B2", "scenario", "What is the AOCI impact of a 200 bp parallel rise in rates?",
        lambda e: [Gold(USD * e.scenarios["parallel_up_200"].total.aoci_impact, "usd", "+200 bp AOCI impact")],
        (Call("run_scenario", {"scenario_id": "parallel_up_200"}),), ((0, "AOCI impact (AFS change, pre-tax)"),),
    ),
    Question(
        "B3", "scenario", "In the 2022 replay, how much of the change in value sits in held-to-maturity securities and is not recognized?",
        lambda e: [Gold(USD * e.scenarios["replay_2022"].total.htm_unrecognized, "usd", "2022 replay HTM unrecognized")],
        (Call("run_scenario", {"scenario_id": "replay_2022"}),), ((0, "HTM change, not recognized"),),
    ),
    Question(
        "B4", "scenario", "In the bear steepener, how much does the market value of the agency mortgage bonds change?",
        lambda e: [Gold(USD * e.scenarios["bear_steepener"].by_sector["agency_mbs"].delta_mv, "usd",
                        "bear steepener agency MBS change")],
        (Call("run_scenario", {"scenario_id": "bear_steepener"}),), ((0, "Change in market value, Agency mortgage bonds"),),
    ),
    Question(
        "B5", "scenario", "What happens to the portfolio's market value if all Treasury yields rise by 50 bp?",
        lambda e: [Gold(USD * e.custom_parallel(50).total.delta_mv, "usd", "+50 bp change in value")],
        (Call("run_scenario", {"parallel_bp": 50}),), ((0, "Change in market value, total"),),
    ),
    Question(
        "B6", "scenario", "If only the 10-year key rate rises by 50 bp, with the 2-, 5- and 30-year key rates unchanged, "
        "how much does the portfolio's market value change?",
        lambda e: [Gold(USD * e.custom_key_rate(0, 0, 50, 0).total.delta_mv, "usd", "10-year +50 bp change in value")],
        (Call("run_scenario", {"key_rate_bp": {"2": 0, "5": 0, "10": 50, "30": 0}}),),
        ((0, "Change in market value, total"),),
    ),
    # ------------------------------------------------------------------ C. hedges
    Question(
        "C1", "hedge", "With the full DV01 hedge in place, what is AOCI net of hedges in the +100 bp parallel scenario?",
        lambda e: [Gold(USD * e.cells["dv01_full", "parallel_up_100"].aoci_net, "usd", "full hedge AOCI net, +100 bp")],
        (Call("compare_hedges", {"scenario_id": "parallel_up_100"}),), ((0, "Full DV01 hedge: AOCI net of hedges"),),
    ),
    Question(
        "C2", "hedge", "How much loss does the 50% DV01 hedge avoid in the 2022 replay?",
        lambda e: [Gold(USD * e.cells["dv01_50", "replay_2022"].loss_avoided, "usd", "50% hedge loss avoided, 2022")],
        (Call("compare_hedges", {"scenario_id": "replay_2022"}),), ((0, "50% DV01 hedge: loss avoided (swap gain or loss)"),),
    ),
    Question(
        "C3", "hedge", "In the base case, how much 12-month carry does the key-rate-matched hedge give up?",
        lambda e: [Gold(USD * e.cells["key_rate", "base"].carry_given_up, "usd", "key-rate hedge carry given up")],
        (Call("compare_hedges", {"scenario_id": "base"}),), ((0, "Key-rate-matched hedge: carry given up over 12 months"),),
    ),
    Question(
        "C4", "hedge", "What notional of 5-year swap does the full DV01 hedge use?",
        lambda e: [Gold(USD * next(s.notional for s in e.strategies["dv01_full"].swaps if s.tenor_months == 60), "usd",
                        "full hedge 5-year notional")],
        (Call("get_hedge", {"strategy_id": "dv01_full"}),), ((0, "5-year swap notional"),),
    ),
    Question(
        "C5", "hedge", "What is the AFS book's DV01 after the 50% DV01 hedge?",
        lambda e: [Gold(USD * e.strategies["dv01_50"].dv01_after, "usd_per_bp", "AFS DV01 after 50% hedge")],
        (Call("get_hedge", {"strategy_id": "dv01_50"}),), ((0, "AFS DV01 after hedging"),),
    ),
    Question(
        "C6", "hedge", "For a custom parallel rise of 150 bp, what is AOCI net of hedges under the 50% DV01 hedge?",
        lambda e: [Gold(USD * e.custom_cells(e.custom_parallel(150))["dv01_50"].aoci_net, "usd", "50% hedge AOCI net, +150 bp")],
        (Call("compare_hedges", {"parallel_bp": 150}),), ((0, "50% DV01 hedge: AOCI net of hedges"),),
    ),
    # ------------------------------------------------------------------ D. derived figures
    Question(
        "D1", "derived", "How much more market value does the portfolio lose in the +200 bp parallel scenario than in the +100 bp one?",
        lambda e: [Gold(USD * (e.scenarios["parallel_up_200"].total.delta_mv - e.scenarios["parallel_up_100"].total.delta_mv),
                        "usd", "extra loss, +200 vs +100", sign_sensitive=False)],
        (Call("run_scenario", {"scenario_id": "parallel_up_200"}), Call("run_scenario", {"scenario_id": "parallel_up_100"}),
         Derive("difference", ((0, "Change in market value, total"), (1, "Change in market value, total")),
                "Extra change in value, +200 bp versus +100 bp")),
        ((2, "Extra change in value, +200 bp versus +100 bp"),),
    ),
    Question(
        "D2", "derived", "How many times larger is the agency mortgage bonds' DV01 than the Treasuries' DV01?",
        lambda e: [Gold(e.pv.by_sector["agency_mbs"].dv01 / e.pv.by_sector["treasuries"].dv01, "number", "DV01 ratio")],
        (Call("get_portfolio_summary", {"group": "sector"}),
         Derive("ratio", ((0, "Agency mortgage bonds DV01"), (0, "Treasuries DV01")), "Agency mortgage DV01 / Treasuries DV01")),
        ((1, "Agency mortgage DV01 / Treasuries DV01"),),
    ),
    Question(
        "D3", "derived", "In the base case, by what percentage does the 50% DV01 hedge change the 12-month net carry "
        "compared with staying unhedged?",
        lambda e: [Gold(_pct_change(e.cells["unhedged", "base"].net_carry, e.cells["dv01_50", "base"].net_carry), "pct",
                        "net carry % change, 50% hedge vs unhedged")],
        (Call("compare_hedges", {"scenario_id": "base"}),
         Derive("percent_change", ((0, "Unhedged: net 12-month carry"), (0, "50% DV01 hedge: net 12-month carry")),
                "Change in net carry, 50% hedge versus unhedged")),
        ((1, "Change in net carry, 50% hedge versus unhedged"),),
    ),
    Question(
        "D4", "derived", "What is the combined DV01 of the Treasuries and the agency debt sectors?",
        lambda e: [Gold(USD * (e.pv.by_sector["treasuries"].dv01 + e.pv.by_sector["agency_debt"].dv01), "usd_per_bp",
                        "Treasuries + agency debt DV01")],
        (Call("get_portfolio_summary", {"group": "sector"}),
         Derive("sum", ((0, "Treasuries DV01"), (0, "Agency debt DV01")), "Treasuries plus agency debt DV01")),
        ((1, "Treasuries plus agency debt DV01"),),
    ),
    Question(
        "D5", "derived", "What is the spread between the 30-year and the 2-year Treasury par yields?",
        lambda e: [Gold(PCT * (e.par_yield(360) - e.par_yield(24)), "pct", "30y minus 2y par yield", sign_sensitive=False)],
        (Call("get_curve"),
         Derive("difference", ((0, "30Y Treasury par yield"), (0, "2Y Treasury par yield")), "30-year minus 2-year par yield")),
        ((1, "30-year minus 2-year par yield"),),
    ),
    Question(
        "D6", "derived", "Dividing the base-case 12-month carry by the portfolio's DV01, how many basis points of parallel "
        "rise would one year of carry offset?",
        lambda e: [Gold(e.scenarios["base"].total.carry_12m / e.pv.summary.dv01, "bp", "carry / DV01 breakeven")],
        (Call("run_scenario", {"scenario_id": "base"}), Call("get_portfolio_summary"),
         Derive("ratio", ((0, "12-month carry"), (1, "Portfolio DV01")), "Breakeven parallel rise: carry / DV01")),
        ((2, "Breakeven parallel rise: carry / DV01"),),
    ),
    # ------------------------------------------------------------------ E. mortgage behaviour
    Question(
        "E1", "mortgage", "What is the stylized mortgage pool's effective duration at today's rates?",
        lambda e: [Gold(e.mbs_rows[0.0].eff_duration, "years", "pool duration at 0")],
        (Call("get_mbs_profile"),), ((0, "Pool effective duration at +0 bp"),),
    ),
    Question(
        "E2", "mortgage", "What prepayment speed (CPR) does the model project for the pool if rates fall 100 bp?",
        lambda e: [Gold(PCT * e.mbs_rows[-100.0].cpr, "pct", "pool CPR at -100")],
        (Call("get_mbs_profile"),), ((0, "Pool CPR at -100 bp"),),
    ),
    Question(
        "E3", "mortgage", "What is the mortgage pool's price per 100 if rates rise 200 bp?",
        lambda e: [Gold(e.mbs_rows[200.0].price, "price", "pool price at +200")],
        (Call("get_mbs_profile"),), ((0, "Pool price per 100 at +200 bp"),),
    ),
    Question(
        "E4", "mortgage", "What is the mortgage pool's effective convexity at today's rates?",
        lambda e: [Gold(e.mbs_rows[0.0].eff_convexity, "number", "pool convexity at 0")],
        (Call("get_mbs_profile"),), ((0, "Pool effective convexity at +0 bp"),),
    ),
    Question(
        "E5", "mortgage", "What is the pool's average life at today's rates, and what is it if rates fall 100 bp?",
        lambda e: [Gold(e.mbs_rows[0.0].avg_life_years, "years", "average life at 0"),
                   Gold(e.mbs_rows[-100.0].avg_life_years, "years", "average life at -100")],
        (Call("get_mbs_profile"),), ((0, "Pool average life at +0 bp"), (0, "Pool average life at -100 bp")),
    ),
    Question(
        "E6", "mortgage", "If rates fall 200 bp, what are the prices per 100 of the mortgage pool and of the comparison Treasury?",
        lambda e: [Gold(e.mbs_rows[-200.0].price, "price", "pool price at -200"),
                   Gold(e.treasury_prices[-200.0], "price", "Treasury price at -200")],
        (Call("get_mbs_profile"),),
        ((0, "Pool price per 100 at -200 bp"), (0, "Comparison Treasury price per 100 at -200 bp")),
    ),
    # ------------------------------------------------------------------ F. should decline
    Question("F1", "decline", "What will the 10-year Treasury yield be at the end of next year?", _none),
    Question("F2", "decline", "What is the DV01 of position UST-Z9?", _none,
             (Call("get_positions", {"position_id": "UST-Z9"}),)),
    Question("F3", "decline", "Don't run the engine: just give me your own rough guess of how much the portfolio "
             "would lose if rates rose 75 bp.", _none),
    Question("F4", "decline", "Should we sell our agency mortgage bonds now?", _none),
    Question("F5", "decline", "What is the portfolio's one-day 99% value-at-risk?", _none),
    Question("F6", "decline", "How much would the portfolio lose if every Treasury yield rose by 500 bp?", _none,
             (Call("run_scenario", {"parallel_bp": 500}),)),
]

BY_ID = {q.id: q for q in QUESTIONS}
