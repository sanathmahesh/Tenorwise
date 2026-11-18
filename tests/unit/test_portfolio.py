"""Model portfolio (PLAN.md section 6, Portfolio; approved list D-036 to D-039).

Valued on the pinned FRED data (Treasury curve 2026-11-16, mortgage spread
2026-11-16).
"""

import pytest

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.analytics.mbs_profile import current_coupon_pool
from tenorwise.portfolio.positions import TOTAL_AMORTIZED_COST_MUSD, load_positions
from tenorwise.portfolio.sources import CLASSES, SECTORS, load_bny_source, mapping_weights
from tenorwise.portfolio.valuation import build_market_context, value_portfolio


@pytest.fixture(scope="module")
def positions():
    return load_positions()


@pytest.fixture(scope="module")
def ctx():
    return build_market_context(fixture_par_curve(), fixture_mortgage_spread())


@pytest.fixture(scope="module")
def pv(positions, ctx):
    return value_portfolio(positions, ctx)


# ------------------------------------------------------------- construction


def test_about_forty_positions_with_unique_ids_each_citing_a_bny_line(positions):
    ids = [p.id for p in positions]
    assert 35 <= len(positions) <= 45
    assert len(ids) == len(set(ids))
    src = load_bny_source()["note2_investment_securities"]
    for p in positions:
        assert p.bny_line in src[p.bny_class], p.id
        assert p.sector in SECTORS and p.klass in CLASSES


def test_total_amortized_cost_is_10_billion(positions):
    total = sum(p.amortized_cost for p in positions)
    assert total == pytest.approx(TOTAL_AMORTIZED_COST_MUSD, rel=5e-3)
    assert TOTAL_AMORTIZED_COST_MUSD == 10_000


def test_sector_and_class_weights_match_the_mapping(positions):
    total = sum(p.amortized_cost for p in positions)
    target = mapping_weights(load_bny_source())
    for (sector, klass), w in target.items():
        got = sum(p.amortized_cost for p in positions if p.sector == sector and p.klass == klass) / total
        assert abs(got - w) < 0.001, (sector, klass, got, w)  # 0.1 percentage point


def test_bonds_bought_at_par_have_amortized_cost_equal_to_face(positions):
    for p in positions:
        assert p.amortized_cost == pytest.approx(p.face, rel=1e-12), p.id


def test_mortgage_pool_shares_reproduce_bnys_line_yields(positions):
    for klass, target in (("AFS", 0.0397), ("HTM", 0.0269)):
        pools = [p for p in positions if p.kind == "mbs" and p.klass == klass]
        avg = sum(p.amortized_cost * p.book_yield for p in pools) / sum(p.amortized_cost for p in pools)
        assert avg == pytest.approx(target, abs=1e-12), klass


def test_labels_stylized_and_proxy(positions):
    for p in positions:
        assert p.stylized == (p.kind == "mbs"), p.id
        if p.sector == "ig_corporates":
            assert p.proxy_for, p.id
            assert "proxy" in p.name.lower(), p.id
        if p.kind == "mbs":
            assert "stylized" in p.name.lower(), p.id


def test_sector_spreads_are_the_approved_values(ctx):
    assert ctx.sector_spreads["treasuries"] == 0.0
    assert ctx.sector_spreads["agency_debt"] == pytest.approx(0.0025, abs=1e-15)
    assert ctx.sector_spreads["ig_corporates"] == pytest.approx(0.0100, abs=1e-15)
    base = bootstrap(fixture_par_curve())
    ms = fixture_mortgage_spread().spread
    pool = current_coupon_pool(base, ms)
    assert pool.price(base, ms, ctx.sector_spreads["agency_mbs"]) == pytest.approx(100.0, abs=1e-9)


# ------------------------------------------------------------- aggregation


def test_portfolio_value_and_dv01_equal_the_sums_of_positions(pv):
    assert pv.summary.market_value == pytest.approx(sum(v.market_value for v in pv.positions), rel=1e-13)
    assert pv.summary.dv01 == pytest.approx(sum(v.dv01 for v in pv.positions), rel=1e-13)
    assert pv.summary.amortized_cost == pytest.approx(sum(v.position.amortized_cost for v in pv.positions), rel=1e-13)
    for bucket in (2, 5, 10, 30):
        assert pv.summary.key_rate_dv01[bucket] == pytest.approx(
            sum(v.key_rate_dv01[bucket] for v in pv.positions), rel=1e-12, abs=1e-12
        )


@pytest.mark.parametrize("grouping", ["by_sector", "by_class"])
def test_groups_add_up_to_the_portfolio(pv, grouping):
    groups = getattr(pv, grouping).values()
    assert sum(g.market_value for g in groups) == pytest.approx(pv.summary.market_value, rel=1e-13)
    assert sum(g.dv01 for g in groups) == pytest.approx(pv.summary.dv01, rel=1e-13)
    assert sum(g.weight for g in groups) == pytest.approx(1.0, abs=1e-13)


def test_portfolio_duration_is_the_value_weighted_average(pv):
    weighted = sum(v.market_value * v.eff_duration for v in pv.positions) / pv.summary.market_value
    assert pv.summary.eff_duration == pytest.approx(weighted, rel=1e-13)
    for name, g in pv.by_sector.items():
        members = [v for v in pv.positions if v.position.sector == name]
        expected = sum(v.market_value * v.eff_duration for v in members) / sum(v.market_value for v in members)
        assert g.eff_duration == pytest.approx(expected, rel=1e-13), name


def test_unrealized_is_market_value_minus_amortized_cost(pv):
    for v in pv.positions:
        assert v.unrealized == pytest.approx(v.market_value - v.position.amortized_cost, abs=1e-9)


def test_average_book_yields_are_reported_against_bnys(pv, positions):
    report = pv.book_yields
    for klass, bny in (("AFS", 0.0357), ("HTM", 0.0258)):
        members = [p for p in positions if p.klass == klass]
        model = sum(p.amortized_cost * p.book_yield for p in members) / sum(p.amortized_cost for p in members)
        assert report[klass]["model"] == pytest.approx(model, abs=1e-15)
        assert report[klass]["bny"] == pytest.approx(bny, abs=1e-15)  # 3.57 / 100 in floating point
        assert report[klass]["gap_bp"] == pytest.approx(1e4 * (model - bny), abs=1e-9)
        # Approved design (D-036): within about 15 bp of BNY's disclosed figure.
        assert abs(report[klass]["gap_bp"]) < 15
