"""Extract every numeric token from an answer (PLAN.md section 9).

Handles signs (including the unicode minus), parentheses for negatives,
currency, thousands separators, decimals, magnitude words and suffixes
(K, M, B, thousand, million, billion), units (%, bp, years, months, per bp),
dash and "to" ranges, and value tags like [[v12]]. Markdown emphasis and list
markers are removed first; ISO dates are reported separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAGNITUDES = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}

_TAG = r"(?:\[\[(?P<tag{n}>v\d+)\]\])"
NUMBER_RE = re.compile(
    r"(?P<open>\()?"
    r"(?P<sign>[+\-−–])?"
    r"(?P<cur>\$)?"
    r"(?<![\w.,])(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
    r"(?:\s?(?P<mag>thousand|million|billion|bn|mn|[KkMB])(?![A-Za-z]))?"
    + _TAG.format(n=1) + "?"
    r"(?P<close>\))?"
    r"(?:\s?(?P<unit>%|bps?(?![A-Za-z])|basis points?|(?:-|\s)?years?(?![A-Za-z])|(?:-|\s)?yrs?(?![A-Za-z])"
    r"|(?:-|\s)?months?(?![A-Za-z])|y(?![A-Za-z])|\s?per bp|/bp))?"
    + _TAG.format(n=2) + "?"
)
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
LIST_MARKER_RE = re.compile(r"(?m)^(\s*)\d+[.)]\s+")


@dataclass
class NumberToken:
    text: str  # as printed, without the tag
    number: float  # the printed number, unsigned, before magnitude
    decimals: int  # digits after the decimal point as printed
    digits: str  # the printed digits without separators, e.g. "412.3"
    magnitude: float  # 1, 1e3, 1e6 or 1e9
    currency: bool
    unit: str | None  # "pct", "bp", "years", "months", "per_bp" or None
    explicit_sign: int | None  # -1, +1 or None
    tag: str | None
    start: int
    end: int


def _unit(raw: str | None) -> str | None:
    if not raw:
        return None
    u = raw.strip().lstrip("-").strip().lower()
    if u == "%":
        return "pct"
    if u.startswith("bp") or u.startswith("basis"):
        return "bp"
    if u.startswith("year") or u.startswith("yr") or u == "y":
        return "years"
    if u.startswith("month"):
        return "months"
    if u in ("per bp", "/bp"):
        return "per_bp"
    return None


def clean(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return LIST_MARKER_RE.sub(lambda m: m.group(1) + "• ", text)


def extract_dates(text: str) -> list[str]:
    return ISO_DATE_RE.findall(clean(text))


def extract_numbers(text: str) -> list[NumberToken]:
    text = ISO_DATE_RE.sub(lambda m: " " * len(m.group(0)), clean(text))
    tokens: list[NumberToken] = []
    for m in NUMBER_RE.finditer(text):
        num = m.group("num")
        digits = num.replace(",", "")
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        mag_raw = m.group("mag")
        magnitude = MAGNITUDES[mag_raw.lower()] if mag_raw else 1.0
        sign_raw = m.group("sign")
        # Parentheses mean negative only for money, so "(as of 2026)" stays positive.
        paren = bool(m.group("open")) and bool(m.group("close")) and (bool(m.group("cur")) or bool(mag_raw))
        explicit = -1 if (paren or (sign_raw in ("-", "−", "–"))) else (1 if sign_raw == "+" else None)
        tag = m.group("tag1") or m.group("tag2")
        printed = m.group(0)
        if tag:
            printed = printed.replace(f"[[{tag}]]", "")
        tokens.append(
            NumberToken(
                text=printed.strip(),
                number=float(digits),
                decimals=decimals,
                digits=digits,
                magnitude=magnitude,
                currency=bool(m.group("cur")),
                unit=_unit(m.group("unit")),
                explicit_sign=explicit,
                tag=tag,
                start=m.start(),
                end=m.end(),
            )
        )
    # Ranges: "2–5 years", "$1.2-1.5M", "2 to 5 years". The dash is a separator,
    # not a sign, and the second number's unit/magnitude/currency carry back.
    for a, b in zip(tokens, tokens[1:]):
        between = text[a.end:b.start]
        dash_range = between == "" and b.explicit_sign == -1 and not b.text.startswith("(")
        word_range = between.strip().lower() == "to" and b.explicit_sign is None
        if dash_range or word_range:
            if dash_range:
                b.explicit_sign = None
                b.text = b.text.lstrip("-−–")
            if a.unit is None:
                a.unit = b.unit
            if a.magnitude == 1.0 and b.magnitude != 1.0:
                a.magnitude = b.magnitude
            a.currency = a.currency or b.currency
    return tokens
