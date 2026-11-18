"""The approved model positions (data/portfolio/positions.json, decision log D-036).

Each position is a design choice, not a holding. Its size is a share of one
BNY line and maturity bucket (10-Q, page 55), scaled so the whole book's
amortized cost is $10,000M. All amounts are in $ millions.

Book yield is the yield at which the bank is assumed to have bought the
position. Amortized cost is the remaining cash flows discounted at the book
yield. Every position is assumed bought at par, so amortized cost equals face:
  - bonds: coupon = book yield, whole half-years to maturity (no accrued);
  - mortgage pools: book yield = the bond-equivalent (semiannual) yield of the
    net coupon, whose monthly-discounted value of any cash-flow stream is par.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from tenorwise.instruments.bond import FixedRateBond
from tenorwise.instruments.mbs import SERVICING_AND_GUARANTEE_FEE, MortgagePool
from tenorwise.paths import DATA_DIR
from tenorwise.portfolio.sources import SECTOR_NAMES, load_bny_source, mapped_amounts

POSITIONS_FILE = DATA_DIR / "portfolio" / "positions.json"
TOTAL_AMORTIZED_COST_MUSD = 10_000

_BNY_CLASS = {"available_for_sale": "AFS", "held_to_maturity": "HTM"}


def bond_equivalent_yield(monthly_coupon: float) -> float:
    """Semiannual yield equivalent to a rate compounded monthly: 2((1 + r/12)^6 - 1)."""
    return 2.0 * ((1.0 + monthly_coupon / 12.0) ** 6 - 1.0)


@dataclass(frozen=True)
class Position:
    id: str
    name: str
    sector: str
    klass: str  # "AFS" or "HTM"
    kind: str  # "bond" or "mbs"
    instrument: FixedRateBond | MortgagePool  # face / balance in $M
    book_yield: float  # decimal, semiannual bond-equivalent
    amortized_cost: float  # $M
    bny_class: str  # "available_for_sale" or "held_to_maturity"
    bny_line: str
    bny_bucket: int | None  # index into the page-55 maturity buckets, None = line total
    share: float  # share of that BNY line-bucket amount
    proxy_for: str | None
    stylized: bool

    @property
    def face(self) -> float:
        i = self.instrument
        return i.face if isinstance(i, FixedRateBond) else i.balance

    @property
    def coupon(self) -> float:
        """Bond coupon, or a pool's net coupon (what the investor receives)."""
        i = self.instrument
        return i.coupon if isinstance(i, FixedRateBond) else i.net_coupon

    @property
    def maturity_months(self) -> int:
        i = self.instrument
        return i.maturity_months if isinstance(i, FixedRateBond) else i.remaining_term_months


def amortized_cost(instrument: FixedRateBond | MortgagePool, book_yield: float) -> float:
    """Remaining cash flows discounted at the book yield (semiannual compounding).

    For a pool bought at par the result is the balance at any prepayment speed,
    so the scheduled (zero-prepayment) cash flows are used; no market data needed.
    """
    if isinstance(instrument, FixedRateBond):
        return instrument.price_from_yield(book_yield)
    cf = instrument.project(np.zeros(instrument.remaining_term_months))
    return float(cf.total @ (1.0 + book_yield / 2.0) ** (-2.0 * cf.times))


def _line_bucket_amount(src: dict[str, Any], bny_class: str, line: str, bucket: int | None) -> float:
    row = src["maturity_distribution_and_yields"][bny_class][line]
    return float(row["total"][0] if bucket is None else row["buckets"][bucket][0])


def _solve_pool_shares(specs: list[dict[str, Any]], src: dict[str, Any]) -> None:
    """Per class, solve the two 'solved' pool shares so the average book yield equals BNY's."""
    md = src["maturity_distribution_and_yields"]
    for bny_class in _BNY_CLASS:
        pools = [s for s in specs if s["kind"] == "mbs" and s["bny"][0] == bny_class]
        if not pools:
            continue
        target = md[bny_class]["Agency RMBS"]["total"][1] / 100.0
        yields = {s["id"]: bond_equivalent_yield(s["wac_pct"] / 100.0 - SERVICING_AND_GUARANTEE_FEE) for s in pools}
        fixed = [s for s in pools if s["split"] != "solved"]
        solved = [s for s in pools if s["split"] == "solved"]
        if len(solved) != 2:
            raise ValueError(f"{bny_class}: expected exactly two 'solved' pool shares")
        rest = 1.0 - sum(s["split"] for s in fixed)
        fixed_part = sum(s["split"] * yields[s["id"]] for s in fixed)
        a, b = solved
        x = (target - fixed_part - rest * yields[b["id"]]) / (yields[a["id"]] - yields[b["id"]])
        if not 0.0 < x < rest:
            raise ValueError(f"{bny_class}: solved pool share {x} is outside (0, {rest})")
        a["split"], b["split"] = x, rest - x


def _name(spec: dict[str, Any], klass: str) -> str:
    if spec["kind"] == "mbs":
        return (
            f"Agency 30y pool, {spec['vintage']} vintage, {spec['wac_pct']:.2f}% WAC "
            f"(stylized) ({klass})"
        )
    m = spec["maturity_months"]
    tenor = f"{m // 12}y{m % 12}m" if m % 12 else f"{m // 12}y"
    label = {
        "treasuries": "US Treasury",
        "agency_debt": "Agency CMBS (as bullet)" if spec["bny"][1] == "Agency commercial MBS" else "Agency note",
        "ig_corporates": f"IG corporate proxy for {spec.get('proxy_for', '')}".strip(),
    }[spec["sector"]]
    return f"{label} {spec['book_yield_pct']:.2f}% {tenor} ({klass})"


def load_positions(path: Path = POSITIONS_FILE, src: dict[str, Any] | None = None) -> list[Position]:
    src = src or load_bny_source()
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    specs = [dict(s) for s in doc["positions"]]
    _solve_pool_shares(specs, src)
    included_total = sum(mapped_amounts(src).values())
    total = float(doc["total_amortized_cost_musd"])

    positions = []
    for s in specs:
        bny_class, line, bucket = s["bny"]
        target_cost = total * _line_bucket_amount(src, bny_class, line, bucket) * s["split"] / included_total
        if s["kind"] == "bond":
            book = s["book_yield_pct"] / 100.0
            unit = FixedRateBond(coupon=book, maturity_months=s["maturity_months"], face=1.0)
            face = target_cost / amortized_cost(unit, book)
            instrument: FixedRateBond | MortgagePool = FixedRateBond(
                coupon=book, maturity_months=s["maturity_months"], face=face
            )
        else:
            wac = s["wac_pct"] / 100.0
            book = bond_equivalent_yield(wac - SERVICING_AND_GUARANTEE_FEE)
            unit = MortgagePool(wac=wac, remaining_term_months=s["remaining_months"], age_months=s["age_months"], balance=1.0)
            face = target_cost / amortized_cost(unit, book)
            instrument = MortgagePool(
                wac=wac, remaining_term_months=s["remaining_months"], age_months=s["age_months"], balance=face
            )
        klass = _BNY_CLASS[bny_class]
        positions.append(
            Position(
                id=s["id"],
                name=_name(s, klass),
                sector=s["sector"],
                klass=klass,
                kind=s["kind"],
                instrument=instrument,
                book_yield=book,
                amortized_cost=amortized_cost(instrument, book),
                bny_class=bny_class,
                bny_line=line,
                bny_bucket=bucket,
                share=float(s["split"]),
                proxy_for=s.get("proxy_for"),
                stylized=s["kind"] == "mbs",
            )
        )
    if any(p.sector not in SECTOR_NAMES for p in positions):
        raise ValueError("unknown sector in positions file")
    return positions
