"""Zero rates at the curve points match a QuantLib piecewise linear-zero curve.

Tolerance, fixed before running: 1e-10 in rate (decimal), i.e. one millionth
of a basis point. Both bootstraps solve each instrument to about 1e-12, so a
correct implementation should leave a wide margin. A failure means the
conventions differ; the fix is the conventions, never the tolerance.
"""

import pytest

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_par_curve

pytest.importorskip("QuantLib")  # skip only if QuantLib itself is missing

from tests.benchmark import quantlib_curve as ql_curve  # noqa: E402  (import errors here must fail, not skip)

ZERO_RATE_TOLERANCE = 1e-10


def test_quantlib_year_fractions_reduce_to_months_over_12():
    for months in fixture_par_curve().tenor_months:
        assert ql_curve.year_fraction(months) == pytest.approx(months / 12, abs=1e-15)


def test_zero_rates_match_quantlib_on_the_fixture_curve():
    par = fixture_par_curve()
    ours = bootstrap(par).zero_rates
    theirs = ql_curve.quantlib_zero_rates(par)

    diffs = [abs(a - b) for a, b in zip(ours, theirs)]
    assert max(diffs) < ZERO_RATE_TOLERANCE, list(zip(par.tenor_months, diffs))
