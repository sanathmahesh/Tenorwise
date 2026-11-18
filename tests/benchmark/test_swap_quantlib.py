"""Swap par rates and values match QuantLib under equivalent conventions.

Par rates on the base curve; values of the base-curve par swaps revalued on
shocked curves. Spreads 0 and 25 bp. Tolerances fixed in quantlib_swaps.py.
"""

import pytest

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.curve.shocks import apply_shock, parallel_shock
from tenorwise.instruments.swap import PayFixedSwap, par_swap_rate

pytest.importorskip("QuantLib")  # skip only if QuantLib itself is missing

from tests.benchmark.quantlib_bonds import ql_curve_handle  # noqa: E402
from tests.benchmark.quantlib_swaps import TOLERANCES, quantlib_swap  # noqa: E402

RATE_TOL = TOLERANCES["swap_par_rate"][0]
VALUE_TOL = TOLERANCES["swap_value"][0]


@pytest.mark.parametrize("months", [24, 60, 120])
@pytest.mark.parametrize("spread", [0.0, 0.0025])
def test_par_rate_matches_quantlib(months, spread):
    curve = bootstrap(fixture_par_curve())
    ours = par_swap_rate(curve, months, spread)
    theirs, npv_at_par = quantlib_swap(ql_curve_handle(curve), months, ours, spread)

    assert abs(ours - theirs) < RATE_TOL
    assert abs(npv_at_par) < VALUE_TOL


@pytest.mark.parametrize("months", [24, 60, 120])
@pytest.mark.parametrize("bp", [-200.0, -25.0, 50.0, 200.0])
@pytest.mark.parametrize("spread", [0.0, 0.0025])
def test_value_after_a_shock_matches_quantlib(months, bp, spread):
    par = fixture_par_curve()
    swap = PayFixedSwap.at_par(bootstrap(par), months, notional=1.0, swap_spread=spread)
    shocked = apply_shock(par, parallel_shock(bp)).curve

    _, theirs = quantlib_swap(ql_curve_handle(shocked), months, swap.fixed_rate, spread)
    assert abs(swap.value(shocked) - theirs) < VALUE_TOL
