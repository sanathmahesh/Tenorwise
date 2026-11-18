"""Number verifier (PLAN.md section 9).

A tagged number passes if the tag exists, the unit is compatible, and either the
text equals the canonical display, or the printed number is the cited value
correctly rounded to the printed precision and within 0.5% of it. An explicit
sign must match. An untagged number passes only if it equals a context number.
"""

import random

import pytest

from tenorwise.agent.ledger import Ledger
from tenorwise.agent.numbers import extract_numbers
from tenorwise.agent.units import display
from tenorwise.agent.verifier import verify


@pytest.fixture
def ledger():
    led = Ledger()
    led.add(-412_345_678.0, "usd", "Change in value", tool="t", args={}, method="m")  # v1  -$412.3M
    led.add(8_648_600_000.0, "usd", "Market value", tool="t", args={}, method="m")  # v2  $8.65B
    led.add(4.93, "pct", "5y swap rate", tool="t", args={}, method="m")  # v3  4.93%
    led.add(25.0, "bp", "Bump", tool="t", args={}, method="m")  # v4  25 bp
    led.add(4.4812, "years", "Duration", tool="t", args={}, method="m")  # v5  4.48 years
    led.add(2_409_200.0, "usd_per_bp", "DV01", tool="t", args={}, method="m")  # v6  $2.4M per bp
    led.add(1_234_567.0, "usd", "Small", tool="t", args={}, method="m")  # v7  $1.2M
    led.add(0.25, "pct", "Quarter percent", tool="t", args={}, method="m")  # v8  0.25%
    led.add(-137.21, "number", "Convexity", tool="t", args={}, method="m")  # v9  -137.21
    for v, unit in ((100, "bp"), (2026, None), (16, None), (12, "months"), (50, "pct"), (2, "years"), (5, "years")):
        led.add_context(v, unit)
    led.add_context_date("2026-11-16")
    return led


def passed(text, ledger):
    checks = verify(text, ledger)
    return bool(checks) and all(c.passed for c in checks)


CASES = [
    # canonical display and correct rounding
    ("falls by -$412.3M[[v1]]", True, "canonical display"),
    ("falls by $412.3M[[v1]]", True, "no explicit sign: magnitude compared"),
    ("falls by $412.35M[[v1]]", True, "more decimals, correctly rounded"),
    ("falls by $412M[[v1]]", True, "fewer decimals, correctly rounded, within 0.5%"),
    # last-digit error
    ("falls by $412.4M[[v1]]", False, "last digit wrong"),
    ("worth $8.66B[[v2]]", False, "last digit wrong ($B)"),
    # $M and $B, K, magnitude words
    ("falls by $0.412B[[v1]]", True, "$B conversion"),
    ("falls by $0.41B[[v1]]", False, "rounds correctly but outside 0.5%"),
    ("worth $8,648.6M[[v2]]", True, "$M with thousands separator"),
    ("worth $8.6486 billion[[v2]]", True, "magnitude word"),
    ("falls by $412,345.7K[[v1]]", True, "$K with thousands separator"),
    # % and bp
    ("at 4.93%[[v3]]", True, "percent"),
    ("at 493 bp[[v3]]", True, "percent cited, printed in bp"),
    ("at 4.9%[[v3]]", False, "outside 0.5% at one decimal"),
    ("by 25 bp[[v4]]", True, "bp"),
    ("by 0.25%[[v4]]", True, "bp cited, printed in percent"),
    ("by 25 bp[[v8]]", True, "percent cited, printed in bp"),
    # negatives and parentheses
    ("a loss of ($412.3M)[[v1]]", True, "parentheses = negative"),
    ("a change of −$412.3M[[v1]]", True, "unicode minus"),
    ("a change of +$412.3M[[v1]]", False, "explicit sign must match"),
    ("convexity of -137.21[[v9]]", True, "negative number"),
    ("convexity of 137.2[[v9]]", True, "unsigned magnitude"),
    # units
    ("duration 4.48 years[[v5]]", True, "years"),
    ("duration 4.5 years[[v5]]", True, "one decimal, within 0.5%"),
    ("rate 4.93 years[[v3]]", False, "incompatible unit"),
    ("DV01 of $2.4M per bp[[v6]]", True, "per bp"),
    ("DV01 of $2.41M[[v6]]", True, "DV01 printed as dollars"),
    ("at 4.93[[v3]]", True, "bare number for a percent"),
    ("worth 8648.6[[v2]]", False, "money needs $ or a magnitude"),
    # tags
    ("falls by $412.3M[[v99]]", False, "unknown tag"),
    ("falls by $412.3M[[v7]]", False, "right number, wrong tag"),
    ("falls by $412.3M", False, "untagged number"),
    # context numbers
    ("if rates rise 100 bp", True, "context number"),
    ("over 12 months", True, "context number"),
    ("as of 16 November 2026", True, "date parts are context"),
    ("as of 2026-11-16", True, "ISO data date is context"),
    ("as of 2025-01-01", False, "unknown date"),
    ("if rates rise 150 bp", False, "untagged, not a context number"),
    # ranges
    ("buckets between 2–5 years", True, "range: both ends are context numbers"),
    ("buckets between 2-5 years", True, "hyphen range"),
    # structure
    ("1. The book falls by $412.3M[[v1]]", True, "list marker is not a number"),
    ("**$412.3M**[[v1]] lost", True, "bold markup"),
    ("$412.3M[[v1]] and $8.66B[[v2]]", False, "one failure blocks the whole answer"),
]


@pytest.mark.parametrize(("text", "expected", "why"), CASES, ids=[c[2] for c in CASES])
def test_verifier_case_table(ledger, text, expected, why):
    assert passed(text, ledger) is expected, [(c.token, c.tag, c.passed, c.reason) for c in verify(text, ledger)]


def test_text_without_numbers_has_no_checks(ledger):
    assert verify("Rates matter. The hedge costs carry.", ledger) == []


def test_ranges_do_not_flip_the_second_number_negative():
    tokens = extract_numbers("between 2–5 years")
    assert [(t.number, t.unit, t.explicit_sign) for t in tokens] == [(2.0, "years", None), (5.0, "years", None)]


def test_tag_digits_and_identifiers_are_not_numbers():
    tokens = extract_numbers("position UST-A2 moved $5.0M[[v12]]")
    assert [t.tag for t in tokens] == ["v12"] and len(tokens) == 1


UNITS = ["usd", "usd_per_bp", "pct", "bp", "years", "months", "price", "number"]


@pytest.mark.parametrize("seed", range(20))
def test_property_canonical_displays_pass_and_last_digit_perturbations_fail(seed):
    rng = random.Random(seed)
    for _ in range(50):
        unit = rng.choice(UNITS)
        scale = {"usd": 10 ** rng.uniform(2, 10), "usd_per_bp": 10 ** rng.uniform(2, 7)}.get(unit, rng.uniform(0.5, 500))
        value = rng.choice([1, -1]) * scale
        led = Ledger()
        v = led.add(value, unit, "x", tool="t", args={}, method="m")
        text = f"value {v.display}[[{v.id}]]"
        assert passed(text, led), text

        # Perturb the last printed digit by one.
        disp = v.display
        idx = max(i for i, ch in enumerate(disp) if ch.isdigit())
        digit = int(disp[idx])
        bumped = disp[:idx] + str((digit + 1) % 10) + disp[idx + 1:]
        if (digit + 1) % 10 == 0:
            bumped = disp[:idx] + str(digit - 1) + disp[idx + 1:]
        assert not passed(f"value {bumped}[[{v.id}]]", led), (disp, bumped)


def test_display_formats_are_the_canonical_strings():
    assert display(-412_345_678.0, "usd") == "-$412.3M"
    assert display(8_648_600_000.0, "usd") == "$8.65B"
    assert display(32_370.0, "usd") == "$32.4K"
    assert display(2_409_200.0, "usd_per_bp") == "$2.4M per bp"
    assert display(4.93, "pct") == "4.93%"
    assert display(33.333, "bp") == "33.3 bp"
    assert display(100.0, "bp") == "100 bp"
    assert display(4.4812, "years") == "4.48 years"
    assert display(-0.0, "pct") == "0.00%"
