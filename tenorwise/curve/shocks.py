"""Rate shocks (PLAN.md section 6, Shocks).

A shock is a number of basis points (1 bp = 0.01 percentage point) added to
each of the 11 par yields, after which the curve is rebuilt from scratch.
Every scenario, effective-duration bump and key-rate bump uses this one
mechanism. Positive basis points mean yields go up.

Key-rate shocks bump one region of the curve using a "tent" over tenor,
centred on 2, 5, 10 or 30 years. The four tents add up to 1 at every tenor,
so bumping all four by the same amount is a parallel shift.

Shocked par yields are floored at 0%, and the result says when the floor binds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from tenorwise.curve.bootstrap import ParCurve, ZeroCurve, bootstrap
from tenorwise.curve.fred import PAR_TENOR_MONTHS

KEY_RATE_BUCKETS: tuple[int, ...] = (2, 5, 10, 30)
_TENT_NODES = np.array(KEY_RATE_BUCKETS, dtype=float)
BP = 1e-4  # one basis point as a decimal rate


def tent_weight(bucket: int, tenor_years: float | np.ndarray) -> float | np.ndarray:
    """Weight of the key-rate tent for `bucket` at a tenor in years.

    Each tent is a straight-line interpolation of a "1 at my node, 0 at the
    others" vector over the nodes 2, 5, 10 and 30 years, held flat outside
    them. So the 2-year tent is 1 up to 2 years and the 30-year tent is 1
    from 30 years on.
    """
    one_hot = (_TENT_NODES == bucket).astype(float)
    if not one_hot.any():
        raise ValueError(f"bucket must be one of {KEY_RATE_BUCKETS}, got {bucket}")
    w = np.interp(tenor_years, _TENT_NODES, one_hot)
    return float(w) if np.ndim(tenor_years) == 0 else w


def parallel_shock(bp: float, n_tenors: int = len(PAR_TENOR_MONTHS)) -> np.ndarray:
    return np.full(n_tenors, float(bp))


def key_rate_shock(
    bucket: int, bp: float, tenor_months: Sequence[int] = PAR_TENOR_MONTHS
) -> np.ndarray:
    tenors = np.array(tenor_months, dtype=float) / 12.0
    return float(bp) * np.asarray(tent_weight(bucket, tenors))


@dataclass(frozen=True)
class ShockedCurve:
    curve: ZeroCurve  # rebuilt from the shocked (and floored) par yields
    shock_bp: tuple[float, ...]
    floor_bound: bool
    floored_tenor_months: tuple[int, ...]


def apply_shock(par: ParCurve, shock_bp: Sequence[float] | np.ndarray) -> ShockedCurve:
    bp = np.asarray(shock_bp, dtype=float)
    if bp.shape != (len(par.tenor_months),):
        raise ValueError(f"shock needs {len(par.tenor_months)} values, got shape {bp.shape}")
    raw = np.array(par.par_yields, dtype=float) + bp * BP
    below_zero = raw < 0.0
    shocked_par = ParCurve(
        data_date=par.data_date,
        tenor_months=par.tenor_months,
        par_yields=tuple(float(v) for v in np.where(below_zero, 0.0, raw)),
    )
    return ShockedCurve(
        curve=bootstrap(shocked_par),
        shock_bp=tuple(float(b) for b in bp),
        floor_bound=bool(below_zero.any()),
        floored_tenor_months=tuple(m for m, hit in zip(par.tenor_months, below_zero) if hit),
    )
