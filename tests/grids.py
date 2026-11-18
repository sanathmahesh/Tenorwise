"""Shared test grid of fixed-rate bonds (synthetic designs, not holdings).

Coupons from 0% to 8%. Maturities from 6 months to 30 years, including
off-cycle maturities (not a multiple of 6 months), which have a short time to
the first coupon and non-zero accrued interest today. Spreads 0 (Treasury-like)
and 1% (credit-like), as continuously compounded additions to the zero rate.
"""

import itertools

COUPONS = (0.0, 0.02, 0.045, 0.06, 0.08)
MATURITY_MONTHS = (6, 7, 12, 18, 23, 24, 37, 60, 61, 84, 117, 120, 123, 179, 240, 299, 360)
SPREADS = (0.0, 0.01)

BOND_GRID = list(itertools.product(COUPONS, MATURITY_MONTHS, SPREADS))
TREASURY_GRID = [(c, m, s) for c, m, s in BOND_GRID if s == 0.0]
SPREAD_GRID = [(c, m, s) for c, m, s in BOND_GRID if s != 0.0]


def grid_id(case: tuple[float, int, float]) -> str:
    c, m, s = case
    return f"c{c * 100:g}%-m{m}-s{s * 1e4:g}bp"
