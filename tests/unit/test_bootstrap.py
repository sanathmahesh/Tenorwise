"""Bootstrap and interpolation (PLAN.md section 6, Curve).

"Fixture" tests use the pinned FRED data in data/fixtures/. Other tests use
synthetic par curves, labelled as such.
"""

import math
from datetime import date

import numpy as np
import pytest

from tenorwise.curve.bootstrap import ParCurve, bootstrap, par_instrument_price
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.curve.fred import PAR_SERIES

TENOR_MONTHS = tuple(m for _, m in PAR_SERIES)


def synthetic_par(yields: list[float]) -> ParCurve:
    return ParCurve(data_date=date(2000, 1, 3), tenor_months=TENOR_MONTHS, par_yields=tuple(yields))


def flat_par(y: float) -> ParCurve:
    return synthetic_par([y] * len(TENOR_MONTHS))


@pytest.fixture(scope="module")
def fixture_curve():
    return bootstrap(fixture_par_curve())


# ------------------------------------------------------------ repricing


def test_every_input_par_instrument_reprices_to_100(fixture_curve):
    par = fixture_curve.par
    for months, y in zip(par.tenor_months, par.par_yields):
        price = par_instrument_price(fixture_curve, months, y)
        assert abs(price - 100.0) < 1e-8, (months, price)


# ------------------------------------------------------------ flat curve


def test_flat_par_curve_gives_flat_zero_curve_from_six_months_out():
    """Synthetic flat 4% par curve.

    From 6 months out, every instrument is semiannual, so the zero curve is
    flat at the continuous equivalent of a 4% semiannual rate: 2*ln(1 + y/2).
    """
    y = 0.04
    curve = bootstrap(flat_par(y))
    expected = 2.0 * math.log1p(y / 2.0)

    for months, z in zip(curve.tenor_months, curve.zero_rates):
        if months >= 6:
            assert z == pytest.approx(expected, abs=1e-12), months


def test_flat_par_curve_short_end_follows_the_simple_interest_convention():
    """Synthetic flat 4% par curve, 1- and 3-month points.

    PLAN.md prices tenors up to 6 months as one payment with simple interest,
    DF = 1/(1 + y*T). The continuous equivalent is ln(1 + y*T)/T, which is not
    2*ln(1 + y/2) except at T = 0.5. So the zero curve is not flat at 1M and 3M.
    See NOTES.md, Phase 1.
    """
    y = 0.04
    curve = bootstrap(flat_par(y))

    for months, z in zip(curve.tenor_months, curve.zero_rates):
        if months < 6:
            t = months / 12
            assert z == pytest.approx(math.log1p(y * t) / t, abs=1e-12), months


# ------------------------------------------------------------ discount factors


def test_discount_factors_are_positive_and_decreasing(fixture_curve):
    t = np.arange(0, 40 * 12 + 1) / 12  # monthly grid out to 40 years
    df = fixture_curve.discount_factor(t)

    assert df[0] == 1.0
    assert np.all(df > 0)
    assert np.all(np.diff(df) < 0)


# ------------------------------------------------------------ interpolation


def test_interpolation_is_exact_at_curve_points(fixture_curve):
    for months, z in zip(fixture_curve.tenor_months, fixture_curve.zero_rates):
        assert fixture_curve.zero_rate(months / 12) == z


def test_interpolation_is_linear_between_curve_points(fixture_curve):
    tenors = np.array(fixture_curve.tenor_months) / 12
    zeros = np.array(fixture_curve.zero_rates)
    for i in range(len(tenors) - 1):
        for w in (0.25, 0.5, 0.75):
            t = (1 - w) * tenors[i] + w * tenors[i + 1]
            expected = (1 - w) * zeros[i] + w * zeros[i + 1]
            assert fixture_curve.zero_rate(t) == pytest.approx(expected, abs=1e-15)


def test_interpolation_is_flat_beyond_the_ends(fixture_curve):
    zeros = fixture_curve.zero_rates
    assert fixture_curve.zero_rate(1 / 365) == zeros[0]
    assert fixture_curve.zero_rate(45.0) == zeros[-1]
    assert fixture_curve.discount_factor(45.0) == pytest.approx(math.exp(-zeros[-1] * 45.0), rel=1e-15)
