"""Shocks: bump the 11 par yields, rebuild the curve (PLAN.md section 6, Shocks)."""

from datetime import date

import numpy as np
import pytest

from tenorwise.curve.bootstrap import ParCurve, bootstrap, par_instrument_price
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.curve.fred import PAR_SERIES
from tenorwise.curve.shocks import (
    KEY_RATE_BUCKETS,
    apply_shock,
    key_rate_shock,
    parallel_shock,
    tent_weight,
)

TENOR_MONTHS = tuple(m for _, m in PAR_SERIES)


@pytest.fixture(scope="module")
def par():
    return fixture_par_curve()


def test_zero_shock_returns_the_same_curve(par):
    base = bootstrap(par)
    shocked = apply_shock(par, parallel_shock(0.0))

    assert shocked.curve.zero_rates == base.zero_rates
    assert shocked.curve.par == par
    assert shocked.floor_bound is False


@pytest.mark.parametrize(
    "shock",
    [
        parallel_shock(100.0),
        parallel_shock(-100.0),
        key_rate_shock(2, 50.0),
        key_rate_shock(10, -75.0),
        key_rate_shock(30, 100.0),
    ],
    ids=["+100 parallel", "-100 parallel", "+50 at 2y", "-75 at 10y", "+100 at 30y"],
)
def test_shocked_par_bonds_reprice_to_100_on_the_shocked_curve(par, shock):
    shocked = apply_shock(par, shock)

    for months, y in zip(shocked.curve.par.tenor_months, shocked.curve.par.par_yields):
        price = par_instrument_price(shocked.curve, months, y)
        assert abs(price - 100.0) < 1e-8, (months, price)


def test_shock_adds_basis_points_to_each_par_yield(par):
    shocked = apply_shock(par, parallel_shock(25.0))

    np.testing.assert_allclose(
        np.array(shocked.curve.par.par_yields) - np.array(par.par_yields), 0.0025, atol=1e-15
    )


# ------------------------------------------------------------ key-rate tents


def test_the_four_tents_sum_to_one_at_every_tenor():
    grid = np.concatenate([np.array(TENOR_MONTHS) / 12, np.linspace(0, 50, 5001)])
    total = sum(tent_weight(bucket, grid) for bucket in KEY_RATE_BUCKETS)

    np.testing.assert_allclose(total, 1.0, atol=1e-15)


@pytest.mark.parametrize(
    ("bucket", "tenor", "expected"),
    [
        (2, 1.0, 1.0), (2, 2.0, 1.0), (2, 3.5, 0.5), (2, 5.0, 0.0),
        (5, 2.0, 0.0), (5, 3.5, 0.5), (5, 5.0, 1.0), (5, 7.5, 0.5), (5, 10.0, 0.0),
        (10, 5.0, 0.0), (10, 7.5, 0.5), (10, 10.0, 1.0), (10, 20.0, 0.5), (10, 30.0, 0.0),
        (30, 10.0, 0.0), (30, 20.0, 0.5), (30, 30.0, 1.0), (30, 40.0, 1.0),
    ],
)
def test_tent_shapes_match_the_plan(bucket, tenor, expected):
    assert tent_weight(bucket, tenor) == pytest.approx(expected, abs=1e-15)


def test_key_rate_shocks_add_up_to_a_parallel_shock():
    total = sum(key_rate_shock(bucket, 10.0) for bucket in KEY_RATE_BUCKETS)

    np.testing.assert_allclose(total, parallel_shock(10.0), atol=1e-12)


# ------------------------------------------------------------ zero floor


def test_floor_at_zero_binds_and_is_flagged():
    """Synthetic curve: 0.5% at the short end, so a -100 bp shock would go negative there."""
    low = ParCurve(
        data_date=date(2000, 1, 3),
        tenor_months=TENOR_MONTHS,
        par_yields=(0.005, 0.005, 0.008, 0.012, 0.015, 0.018, 0.02, 0.022, 0.025, 0.028, 0.03),
    )

    shocked = apply_shock(low, parallel_shock(-100.0))

    assert shocked.floor_bound is True
    assert shocked.floored_tenor_months == (1, 3, 6)
    assert min(shocked.curve.par.par_yields) == 0.0
    assert all(y >= 0.0 for y in shocked.curve.par.par_yields)


def test_floor_not_flagged_when_it_does_not_bind(par):
    assert apply_shock(par, parallel_shock(-100.0)).floor_bound is False
