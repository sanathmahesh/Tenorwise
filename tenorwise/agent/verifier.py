"""Verify every number in the model's text against the ledger (PLAN.md section 9).

A tagged number passes if the tag exists, the unit is compatible, and either
the text equals the canonical display, or the printed number is the cited value
correctly rounded to the printed precision and within 0.5% of it. An explicit
sign must match. An untagged number passes only if it equals a context number.
Anything else fails, and one failure blocks the whole answer.

What this proves: each number came from the engine and was copied correctly.
It does not prove the sentence around the number is right (LIMITATIONS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from tenorwise.agent.ledger import Ledger, LedgerValue
from tenorwise.agent.numbers import NumberToken, extract_dates, extract_numbers

RELATIVE_TOLERANCE = 0.005
TOLERANCE_TEXT = (
    "Every number in an answer is checked against the engine before it is shown. A tagged number must equal "
    "the cited value's display string, or be that value correctly rounded to the printed precision and within "
    "0.5% of it; an explicit sign must match. An untagged number must be a context number (a tool argument, "
    "tenor, shock size, hedge ratio, horizon or date). One failure blocks the answer."
)


@dataclass(frozen=True)
class Check:
    token: str
    tag: str | None
    passed: bool
    reason: str


def _norm(s: str) -> str:
    return s.replace("−", "-").replace("–", "-").replace(" ", "").strip("()")


def _scale(tok: NumberToken, cited_unit: str) -> float | None:
    """Factor k such that the printed number should approximate |cited value| * k; None if incompatible."""
    money = tok.currency or tok.magnitude != 1.0
    unit = tok.unit
    if cited_unit in ("usd", "usd_per_bp"):
        if not money or unit not in (None, "per_bp"):
            return None
        if unit == "per_bp" and cited_unit != "usd_per_bp":
            return None
        return 1.0 / tok.magnitude
    if money or unit == "per_bp":
        return None
    if cited_unit == "pct":
        return {None: 1.0, "pct": 1.0, "bp": 100.0}.get(unit)
    if cited_unit == "bp":
        return {None: 1.0, "bp": 1.0, "pct": 0.01}.get(unit)
    if cited_unit in ("years", "months"):
        return 1.0 if unit in (None, cited_unit) else None
    if cited_unit in ("price", "number"):
        return 1.0 if unit is None else None
    return None


def _rounds_to(value: float, digits: str, decimals: int) -> bool:
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(repr(value))
    printed = Decimal(digits)
    return any(d.quantize(q, rounding=r) == printed for r in (ROUND_HALF_UP, ROUND_HALF_EVEN))


def check_tagged(tok: NumberToken, v: LedgerValue) -> Check:
    if _norm(tok.text) == _norm(v.display):
        return Check(tok.text, v.id, True, "matches the cited display")
    k = _scale(tok, v.unit)
    if k is None:
        return Check(tok.text, v.id, False, f"unit does not match {v.id} ({v.unit}, displayed {v.display})")
    cited = v.value * k
    if tok.explicit_sign is not None and cited != 0 and (tok.explicit_sign > 0) != (cited > 0):
        return Check(tok.text, v.id, False, f"sign does not match {v.id} ({v.display})")
    c = abs(cited)
    if not _rounds_to(c, tok.digits, tok.decimals):
        return Check(tok.text, v.id, False, f"not {v.id} rounded to the printed precision; copy {v.display}")
    if (c == 0 and tok.number != 0) or abs(tok.number - c) > RELATIVE_TOLERANCE * c:
        return Check(tok.text, v.id, False, f"more than 0.5% from {v.id}; copy {v.display}")
    return Check(tok.text, v.id, True, "correctly rounded, within 0.5%")


def _context_compatible(tok_unit: str | None, ctx_unit: str | None) -> bool:
    return tok_unit is None or ctx_unit is None or tok_unit == ctx_unit


def check_untagged(tok: NumberToken, ledger: Ledger) -> Check:
    if not (tok.currency or tok.magnitude != 1.0):
        value = tok.number * (-1 if tok.explicit_sign == -1 else 1)
        for c in ledger.context:
            same = abs(value - c.value) < 1e-9 if tok.explicit_sign is not None else abs(abs(value) - abs(c.value)) < 1e-9
            if same and _context_compatible(tok.unit, c.unit):
                return Check(tok.text, None, True, "context number")
    return Check(tok.text, None, False, "untagged number that is not a context number; cite a value with its [[v…]] tag")


def verify(text: str, ledger: Ledger) -> list[Check]:
    checks: list[Check] = []
    for iso in extract_dates(text):
        ok = iso in ledger.context_dates
        checks.append(Check(iso, None, ok, "context date" if ok else "date not from the data"))
    for tok in extract_numbers(text):
        if tok.tag is None:
            checks.append(check_untagged(tok, ledger))
        elif tok.tag not in ledger.values:
            checks.append(Check(tok.text, tok.tag, False, f"unknown tag {tok.tag}"))
        else:
            checks.append(check_tagged(tok, ledger.values[tok.tag]))
    return checks


def all_passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)
