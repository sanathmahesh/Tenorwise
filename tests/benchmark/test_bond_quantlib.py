"""Price, yield, Macaulay and modified duration and convexity match QuantLib.

Grid: coupons 0% to 8%, maturities 6 months to 30 years including off-cycle
maturities, spreads 0 and 1% (tests/grids.py). Tolerances are fixed in
tests/benchmark/quantlib_bonds.py; the fix for a failure is the conventions,
never the tolerance.
"""

import pytest

from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_par_curve
from tests.grids import BOND_GRID, grid_id

pytest.importorskip("QuantLib")  # skip only if QuantLib itself is missing

from tests.benchmark import quantlib_bonds as qb  # noqa: E402  (import errors here must fail, not skip)


@pytest.fixture(scope="module")
def curve():
    return bootstrap(fixture_par_curve())


@pytest.fixture(scope="module")
def handle(curve):
    return qb.ql_curve_handle(curve)


@pytest.mark.parametrize("case", BOND_GRID, ids=grid_id)
def test_bond_measures_match_quantlib(curve, handle, case):
    ours = qb.tenorwise_measures(curve, *case)
    theirs = qb.quantlib_measures(handle, *case)

    for name, (tolerance, unit) in qb.TOLERANCES.items():
        assert abs(ours[name] - theirs[name]) < tolerance, (name, unit, ours[name], theirs[name])
