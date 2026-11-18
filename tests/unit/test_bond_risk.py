"""Curve-based risk: effective duration and convexity, DV01, key-rate DV01s.

All measures come from bump-and-reprice on the shocked curve (PLAN.md
section 6): effective measures use +/-25 bp parallel shocks, DV01 uses
+/-1 bp, and key-rate measures use +/-1 bp on each tent. Shocks move the
par yields and the curve is rebuilt.

Thresholds were fixed before the code was written:
  - formula DV01 vs bump-and-reprice: 0.1% (PLAN.md). The two measure the
    same thing only on a flat par curve, so that is where they are compared
    (with a spread s they differ by the compounding factor exp(s/2)). On the
    real, upward-sloping curve, a 1 bp par-yield shift moves a bond's own
    yield by more than 1 bp; the test there checks that this fully explains
    the gap (PLAN.md wording changed by owner decision D-024);
  - duration + convexity predicting a +/-100 bp reprice: error at most 2.5% of
    the actual change. The error is the third-order term, largest for the
    30-year zero-coupon bond (about 1.7% for a continuously compounded zero);
  - key-rate durations sum to effective duration within 0.5% (PLAN.md).
"""

import math
from datetime import date

import pytest

from tenorwise.analytics.risk import (
    DV01_BUMP_BP,
    KEY_RATE_BUCKETS,
    build_risk_curves,
    risk_measures,
)
from tenorwise.curve.bootstrap import ParCurve
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.curve.fred import PAR_TENOR_MONTHS
from tenorwise.curve.shocks import BP, apply_shock, parallel_shock
from tenorwise.instruments.bond import FixedRateBond
from tests.grids import BOND_GRID, SPREAD_GRID, TREASURY_GRID, grid_id


@pytest.fixture(scope="module")
def par():
    return fixture_par_curve()


@pytest.fixture(scope="module")
def curves(par):
    return build_risk_curves(par)


@pytest.fixture(scope="module")
def flat_curves():
    """Synthetic flat 5% par curve: here a 1 bp par shift moves every bond's
    own yield by (almost exactly) 1 bp, so formula and bump DV01 coincide."""
    flat = ParCurve(data_date=date(2000, 1, 3), tenor_months=PAR_TENOR_MONTHS, par_yields=(0.05,) * 11)
    return build_risk_curves(flat)


@pytest.fixture(scope="module")
def shifted_100(par):
    return {bp: apply_shock(par, parallel_shock(bp)).curve for bp in (-100.0, 100.0)}


def measures(curves, coupon, months, spread, face=100.0):
    bond = FixedRateBond(coupon=coupon, maturity_months=months, face=face)
    return bond, risk_measures(lambda c: bond.dirty_price(c, spread), curves)


def formula_dv01(bond, dirty):
    """Analytic DV01 from the bond's own yield: modified duration x price x 1 bp."""
    return bond.modified_duration(bond.yield_from_price(dirty)) * dirty * 1e-4


def own_yield_move_bp(bond, curves, spread):
    """How many bp the bond's own yield moves per 1 bp move in par yields."""
    up = bond.yield_from_price(bond.dirty_price(curves.parallel[DV01_BUMP_BP], spread))
    down = bond.yield_from_price(bond.dirty_price(curves.parallel[-DV01_BUMP_BP], spread))
    return (up - down) / (2 * DV01_BUMP_BP * BP)


@pytest.mark.parametrize("case", TREASURY_GRID, ids=grid_id)
def test_formula_dv01_matches_bump_and_reprice_on_a_flat_curve(flat_curves, case):
    bond, r = measures(flat_curves, *case)

    assert formula_dv01(bond, r.price) == pytest.approx(r.dv01, rel=1e-3)


@pytest.mark.parametrize("case", SPREAD_GRID, ids=grid_id)
def test_with_a_spread_the_flat_curve_gap_is_the_compounding_factor(flat_curves, case):
    """A continuously compounded spread s scales the bond's semiannual yield
    move per 1 bp of par yield by exp(s/2), so the two DV01s differ by that
    factor. Checked to the same 0.1%."""
    bond, r = measures(flat_curves, *case)
    spread = case[2]

    assert formula_dv01(bond, r.price) * math.exp(spread / 2) == pytest.approx(r.dv01, rel=1e-3)


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_on_the_real_curve_the_dv01_gap_is_the_bonds_own_yield_move(curves, case):
    """On the upward-sloping pinned curve a 1 bp par shift moves long bonds'
    own yields by more than 1 bp (up to about 1.045 bp for a 20-year zero).
    Formula DV01 x that move must reproduce the bump DV01 within 0.1%."""
    bond, r = measures(curves, *case)
    move = own_yield_move_bp(bond, curves, case[2])

    assert formula_dv01(bond, r.price) * move == pytest.approx(r.dv01, rel=1e-3)


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_duration_and_convexity_predict_a_100bp_reprice(curves, shifted_100, case):
    bond, r = measures(curves, *case)
    spread = case[2]
    for bp, curve in shifted_100.items():
        dy = bp * 1e-4
        actual = bond.dirty_price(curve, spread) - r.price
        duration_only = -r.eff_duration * dy * r.price
        with_convexity = duration_only + 0.5 * r.eff_convexity * dy**2 * r.price

        assert abs(with_convexity - actual) <= 0.025 * abs(actual), bp
        assert abs(with_convexity - actual) < abs(duration_only - actual), bp


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_effective_convexity_is_positive(curves, case):
    _, r = measures(curves, *case)

    assert r.eff_convexity > 0


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_key_rate_durations_sum_to_effective_duration(curves, case):
    _, r = measures(curves, *case)

    assert sum(r.key_rate_duration.values()) == pytest.approx(r.eff_duration, rel=5e-3)


def test_two_year_bond_risk_sits_in_the_two_year_bucket(curves):
    _, r = measures(curves, 0.045, 24, 0.0)

    assert r.key_rate_duration[2] == pytest.approx(r.eff_duration, rel=5e-3)
    for bucket in KEY_RATE_BUCKETS:
        if bucket != 2:
            assert r.key_rate_dv01[bucket] == 0.0


def test_dv01_is_positive_for_a_long_bond_and_scales_with_face(curves):
    _, small = measures(curves, 0.045, 123, 0.0, face=100.0)
    _, big = measures(curves, 0.045, 123, 0.0, face=1_000_000.0)

    assert small.dv01 > 0 and small.eff_duration > 0
    assert big.dv01 == pytest.approx(10_000 * small.dv01, rel=1e-12)
    assert big.eff_duration == pytest.approx(small.eff_duration, rel=1e-12)


def test_risk_curves_report_no_floor_on_the_pinned_curve(curves):
    assert curves.floor_bound is False
