"""Check that every number in a document traces to the project's measured results.

"Traces" uses the analyst's own number parser and verification rule: each number
printed must be some value from the source files, correctly rounded to the printed
precision and within 0.5%. Document identifiers (SR 26-2, NIST AI 600-1, section
numbers, decision and assumption IDs), written dates of sources, links and code
spans are not figures and are removed first. Numbers in scientific notation
("1.54 × 10⁻¹³"), which the parser cannot read, are checked by the same rule.
Used by the strategy, model card and RESULTS.md tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tenorwise.agent.ledger import Ledger
from tenorwise.agent.numbers import extract_dates, extract_numbers
from tenorwise.agent.verifier import check_tagged

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "docs" / "evidence" / "evals"
QUANTLIB = REPO / "docs" / "evidence" / "quantlib_report.json"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
IDENTIFIERS = [
    r"`[^`]*`",  # code spans: model IDs, file paths, test names
    r"https?://\S+",  # links
    rf"\b(?:\d{{1,2}} )?(?:{MONTHS}) \d{{4}}\b",  # written dates of sources, e.g. 17 April 2026
    r"\bSR \d+-\d+\b", r"\bSR 11-7\b", r"\bNIST AI \d+-\d+\b", r"\bOCC Bulletin \d+-\d+\b", r"\bFIL-\d+-\d+\b",
    r"\bCircular \d+-\d+\b", r"\bASC \d+\b", r"\b12 CFR [\d.()a-z]+",
    r"\b[Ff]ootnote \d+\b", r"\b[Ss]ections? \d+(?:\.\d+)*\b", r"\b[A-Z]-\d+\b",
    r"\b[A-F]\d\b",  # question IDs, e.g. E1
    r"^\s*\|?\s*\d+\s*\|", r"(?m)^#+ \d+\.",  # row and heading numbers
]


def strip_identifiers(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    for pattern in IDENTIFIERS:
        text = re.sub(pattern, " ", text, flags=re.M)
    return text


def eval_ledger() -> tuple[Ledger, set[str]]:
    """Every figure in the eval results, in the units a document would print it."""
    summary = json.loads((EVALS / "summary.json").read_text())
    led = Ledger()
    dates = set()

    def add(value, unit, label):
        led.add(value, unit, label, tool="eval", args={}, method="eval")

    add(len(summary["questions"]), "number", "questions")
    add(100 * summary["upper_bound_confidence"], "pct", "confidence level of the upper bounds")
    for m in summary["models"]:
        for k, v in m.items():
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)):
                if k.endswith("_ms"):
                    add(v / 1000, "number", f"{m['id']} {k} in seconds")
                elif k.endswith("_usd"):
                    add(v, "usd", f"{m['id']} {k}")
                elif "rate" in k or k.startswith("accuracy") or k.endswith("upper_95"):
                    add(100 * v, "pct", f"{m['id']} {k}")
                else:
                    add(v, "number", f"{m['id']} {k}")
            elif isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, (int, float)):
                        add(100 * vv if k.startswith("accuracy") else vv, "pct" if k.startswith("accuracy") else "number",
                            f"{m['id']} {k} {kk}")
        dates.update(m["prices_read_on"])
    for path in sorted((EVALS / "raw").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            dates.add(json.loads(line)["finished_at"][:10])
    return led, dates


def quantlib_values(led: Ledger) -> None:
    report = json.loads(QUANTLIB.read_text())
    for row in report["quantlib"]:
        led.add(row["max_abs_diff"], "number", row["measure"], tool="quantlib", args={}, method="quantlib")
        led.add(row["instruments"], "number", row["measure"] + " instruments", tool="quantlib", args={}, method="quantlib")


SUPERSCRIPT = str.maketrans("⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹", "-+0123456789")
SCIENTIFIC = re.compile(r"(\d+(?:\.\d+)?) × 10([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)")


def _sci_traces(mantissa: str, exponent: str, led: Ledger) -> bool:
    """"1.54 × 10⁻¹³" passes if some source value, written to the same significant figures, prints the same
    and is within 0.5% (the verifier's rule, for numbers the extractor cannot read)."""
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    printed = float(mantissa) * 10 ** int(exponent.translate(SUPERSCRIPT))
    for v in led.values.values():
        m, e = f"{abs(v.value):.{decimals}e}".split("e")
        if m == mantissa and int(e) == int(exponent.translate(SUPERSCRIPT)) and abs(printed - abs(v.value)) <= 0.005 * abs(v.value):
            return True
    return False


def untraced(text: str, led: Ledger, dates: set[str]) -> list[str]:
    bad = [m.group(0) for m in SCIENTIFIC.finditer(text) if not _sci_traces(m.group(1), m.group(2), led)]
    text = SCIENTIFIC.sub(" ", text)
    clean = strip_identifiers(text)
    bad += [d for d in extract_dates(clean) if d not in dates]
    clean = re.sub(r"\d{4}-\d{2}-\d{2}", " ", clean)
    for tok in extract_numbers(clean):
        if not any(check_tagged(tok, v).passed for v in led.values.values()):
            bad.append(tok.text)
    return bad
