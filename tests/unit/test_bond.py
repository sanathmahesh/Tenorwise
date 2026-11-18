"""Fixed-rate bond pricing and yield-based measures (PLAN.md section 6, Fixed-rate bonds).

Bonds here are synthetic test designs priced on the pinned FRED curve.
"""

import pytest

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.instruments.bond import FixedRateBond
from tests.grids import BOND_GRID, grid_id


@pytest.fixture(scope="module")
def curve():
    return bootstrap(fixture_par_curve())


def test_par_bond_prices_to_100_on_the_curve(curve):
    """A bond with the curve's own par yield as coupon, at a curve tenor, is a par bond."""
    for months, y in zip(curve.tenor_months, curve.par.par_yields):
        if months >= 12:
            bond = FixedRateBond(coupon=y, maturity_months=months)
            assert abs(bond.dirty_price(curve) - 100.0) < 1e-8, months


@pytest.mark.parametrize("months", [6, 12, 60, 360])
def test_par_bond_prices_to_100_at_its_own_yield(months):
    bond = FixedRateBond(coupon=0.05, maturity_months=months)

    assert bond.price_from_yield(0.05) == pytest.approx(100.0, abs=1e-10)


@pytest.mark.parametrize("months", [6, 7, 61, 123, 360])
def test_zero_coupon_bond_macaulay_duration_equals_maturity(curve, months):
    bond = FixedRateBond(coupon=0.0, maturity_months=months)
    y = bond.yield_from_price(bond.dirty_price(curve))

    assert bond.macaulay_duration(y) == pytest.approx(months / 12, abs=1e-12)


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_price_to_yield_to_price_round_trips(curve, case):
    coupon, months, spread = case
    bond = FixedRateBond(coupon=coupon, maturity_months=months)
    dirty = bond.dirty_price(curve, spread)

    assert bond.price_from_yield(bond.yield_from_price(dirty)) == pytest.approx(dirty, abs=1e-9)


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_clean_plus_accrued_equals_dirty(curve, case):
    coupon, months, spread = case
    bond = FixedRateBond(coupon=coupon, maturity_months=months)

    assert bond.clean_price(curve, spread) + bond.accrued_interest() == pytest.approx(
        bond.dirty_price(curve, spread), abs=1e-12
    )


@pytest.mark.parametrize(
    ("months", "expected"),
    [(120, 0.0), (123, 1.5), (121, 2.5), (125, 0.5), (7, 2.5)],
)
def test_accrued_interest_is_coupon_times_fraction_of_half_year_elapsed(months, expected):
    """6% coupon on 100 face = 3.00 per half-year. 123 months: next coupon in 3
    months, so 3 of 6 months have elapsed and accrued is 1.50."""
    assert FixedRateBond(coupon=0.06, maturity_months=months).accrued_interest() == pytest.approx(
        expected, abs=1e-12
    )


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_convexity_is_positive(curve, case):
    coupon, months, spread = case
    bond = FixedRateBond(coupon=coupon, maturity_months=months)
    y = bond.yield_from_price(bond.dirty_price(curve, spread))

    assert bond.convexity(y) > 0


def test_modified_duration_is_macaulay_over_one_plus_half_yield(curve):
    bond = FixedRateBond(coupon=0.045, maturity_months=123)
    y = bond.yield_from_price(bond.dirty_price(curve))

    assert bond.modified_duration(y) == pytest.approx(bond.macaulay_duration(y) / (1 + y / 2), rel=1e-15)


def test_spread_lowers_the_price(curve):
    bond = FixedRateBond(coupon=0.045, maturity_months=120)

    assert bond.dirty_price(curve, 0.01) < bond.dirty_price(curve, 0.0)


def test_face_scales_price_linearly(curve):
    small = FixedRateBond(coupon=0.045, maturity_months=123, face=100.0)
    big = FixedRateBond(coupon=0.045, maturity_months=123, face=1_000_000.0)

    assert big.dirty_price(curve) == pytest.approx(10_000 * small.dirty_price(curve), rel=1e-14)
    assert big.accrued_interest() == pytest.approx(10_000 * small.accrued_interest(), rel=1e-14)
