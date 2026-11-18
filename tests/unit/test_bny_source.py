"""BNY 10-Q transcription and the model-sector mapping (PLAN.md section 6, Portfolio).

The transcription is hand-typed from the filing, so these tests check it
against the filing's own arithmetic: each line's amortized cost + gains -
losses = fair value, lines sum to the printed totals, and maturity buckets sum
to the printed bucket totals.
"""

import pytest

from tenorwise.portfolio.sources import (
    EXCLUDED_LINES,
    SECTOR_MAPPING,
    SECTORS,
    load_bny_source,
    mapped_amounts,
    mapping_weights,
)

AC, GAINS, LOSSES, FV = range(4)


@pytest.fixture(scope="module")
def src():
    return load_bny_source()


def test_citation_is_complete(src):
    c = src["citation"]
    assert c["pdf_url"].startswith("https://www.bny.com/")
    assert c["filing_date"] == "2026-10-30"
    assert c["period_ended"] == "2026-09-30"
    assert len(c["pdf_sha256"]) == 64
    assert "page 52" in src["note2_investment_securities"]["source"]
    assert "page 55" in src["maturity_distribution_and_yields"]["source"]
    assert "page 79" in src["note14_hedging"]["source"]


@pytest.mark.parametrize("klass", ["available_for_sale", "held_to_maturity"])
def test_each_line_amortized_cost_plus_gains_minus_losses_is_fair_value(src, klass):
    for name, row in src["note2_investment_securities"][klass].items():
        assert row[AC] + row[GAINS] - row[LOSSES] == row[FV], name


def test_transcribed_lines_sum_to_bny_totals(src):
    n2 = src["note2_investment_securities"]
    afs_sum = [sum(col) for col in zip(*n2["available_for_sale"].values())]
    htm_sum = [sum(col) for col in zip(*n2["held_to_maturity"].values())]

    assert afs_sum == n2["available_for_sale_total_excluding_portfolio_level_basis_adjustments"]
    assert [a + b for a, b in zip(afs_sum, n2["available_for_sale_portfolio_level_basis_adjustments"])] == n2[
        "available_for_sale_total"
    ]
    assert htm_sum == n2["held_to_maturity_total"]
    assert [a + b for a, b in zip(n2["available_for_sale_total"], n2["held_to_maturity_total"])] == n2[
        "total_investment_securities"
    ]
    # The plan's checked figures (PLAN.md section 4).
    assert n2["available_for_sale_total"][FV] == 105_252
    assert n2["held_to_maturity_total"][AC] == 46_732


@pytest.mark.parametrize("klass", ["available_for_sale", "held_to_maturity"])
def test_maturity_table_buckets_sum_to_bucket_totals(src, klass):
    md = src["maturity_distribution_and_yields"]
    rows = md[klass]
    total = md[f"{klass}_total"]
    for i in range(4):
        bucketed = sum(r["buckets"][i][0] for r in rows.values() if r["buckets"] is not None)
        assert bucketed == total["buckets"][i][0], (klass, i)
    assert sum(r["total"][0] for r in rows.values()) == total["total"][0]


def test_maturity_table_amounts_match_note2_carrying_amounts(src):
    n2 = src["note2_investment_securities"]
    md = src["maturity_distribution_and_yields"]
    for name, row in md["available_for_sale"].items():
        assert row["total"][0] == n2["available_for_sale"][name][FV], name  # AFS carried at fair value
    for name, row in md["held_to_maturity"].items():
        assert row["total"][0] == n2["held_to_maturity"][name][AC], name  # HTM carried at amortized cost
    assert md["available_for_sale_total"]["total"][1] == 3.57
    assert md["held_to_maturity_total"]["total"][1] == 2.58


def test_every_bny_line_is_mapped_or_excluded_exactly_once(src):
    n2 = src["note2_investment_securities"]
    all_lines = set(n2["available_for_sale"]) | set(n2["held_to_maturity"])
    mapped = [line for lines in SECTOR_MAPPING.values() for line in lines]

    assert len(mapped) == len(set(mapped))
    assert set(mapped).isdisjoint(EXCLUDED_LINES)
    assert set(mapped) | set(EXCLUDED_LINES) == all_lines
    assert set(EXCLUDED_LINES) == {"Non-US government", "CLOs"}


def test_mapped_amounts_follow_the_plan(src):
    amounts = mapped_amounts(src)
    assert amounts[("treasuries", "AFS")] == 30_088
    assert amounts[("agency_mbs", "HTM")] == 29_178
    assert amounts[("agency_debt", "AFS")] == 1_494 + 6_183
    assert amounts[("ig_corporates", "HTM")] == 526 + 11


def test_recomputed_weights_match_the_plans_expected_weights(src):
    """PLAN.md: Treasuries 31.8% (27.2 / 4.6), agency mortgage 45.8% (19.4 / 26.4),
    agency debt 11.3% (6.9 / 4.4), IG corporates 11.0% (10.5 / 0.5)."""
    w = mapping_weights(src)
    expected = {
        "treasuries": (31.8, 27.2, 4.6),
        "agency_mbs": (45.8, 19.4, 26.4),
        "agency_debt": (11.3, 6.9, 4.4),
        "ig_corporates": (11.0, 10.5, 0.5),
    }
    for sector, (total, afs, htm) in expected.items():
        assert round(100 * (w[(sector, "AFS")] + w[(sector, "HTM")]), 1) == total, sector
        assert round(100 * w[(sector, "AFS")], 1) == afs, sector
        assert round(100 * w[(sector, "HTM")], 1) == htm, sector
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-15)
    assert set(SECTORS) == set(expected)
