"""Measure agreement with QuantLib and write docs/evidence/quantlib_report.json.

    uv run python scripts/quantlib_report.py

Dev-only (QuantLib is a dev dependency). Uses the pinned FRED fixture, so the
report is reproducible. Every number in the report is measured by this run.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import QuantLib as ql  # noqa: E402

from tenorwise.curve.bootstrap import bootstrap  # noqa: E402
from tenorwise.curve.fixture import PINNED_FIXTURE, fixture_par_curve  # noqa: E402
from tests.benchmark.quantlib_bonds import TOLERANCES, bond_differences  # noqa: E402
from tenorwise.curve.shocks import apply_shock, parallel_shock  # noqa: E402
from tenorwise.instruments.swap import PayFixedSwap, par_swap_rate  # noqa: E402
from tests.benchmark.quantlib_bonds import ql_curve_handle  # noqa: E402
from tests.benchmark.quantlib_curve import quantlib_zero_rates  # noqa: E402
from tests.benchmark.quantlib_swaps import TOLERANCES as SWAP_TOLERANCES  # noqa: E402
from tests.benchmark.quantlib_swaps import quantlib_swap  # noqa: E402

from tests.grids import BOND_GRID, COUPONS, MATURITY_MONTHS, SPREADS  # noqa: E402

OUT = REPO_ROOT / "docs" / "evidence" / "quantlib_report.json"
CURVE_TOLERANCE = 1e-10  # same as tests/benchmark/test_curve_quantlib.py
SWAP_TENORS = (24, 60, 120)
SWAP_SPREADS = (0.0, 0.0025)
SWAP_SHOCKS_BP = (-200.0, -25.0, 50.0, 200.0)


def main() -> int:
    par = fixture_par_curve()
    curve = bootstrap(par)

    zero_diffs = [abs(a - b) for a, b in zip(curve.zero_rates, quantlib_zero_rates(par))]
    measures = [
        {
            "measure": "zero_rate",
            "description": "Bootstrapped zero rate at each of the 11 curve points vs QuantLib PiecewiseLinearZero",
            "instruments": len(zero_diffs),
            "max_abs_diff": max(zero_diffs),
            "unit": "decimal rate",
            "tolerance": CURVE_TOLERANCE,
        }
    ]
    for name, diffs in bond_differences(curve, BOND_GRID).items():
        tolerance, unit = TOLERANCES[name]
        measures.append(
            {
                "measure": name,
                "description": f"Fixed-rate bond {name.replace('_', ' ')} vs QuantLib on the same zero curve",
                "instruments": len(diffs),
                "max_abs_diff": max(diffs),
                "unit": unit,
                "tolerance": tolerance,
            }
        )

    rate_diffs, value_diffs = [], []
    handle = ql_curve_handle(curve)
    for months in SWAP_TENORS:
        for spread in SWAP_SPREADS:
            ours = par_swap_rate(curve, months, spread)
            theirs, _ = quantlib_swap(handle, months, ours, spread)
            rate_diffs.append(abs(ours - theirs))
            swap = PayFixedSwap.at_par(curve, months, notional=1.0, swap_spread=spread)
            for bp in SWAP_SHOCKS_BP:
                shocked = apply_shock(par, parallel_shock(bp)).curve
                _, ql_value = quantlib_swap(ql_curve_handle(shocked), months, swap.fixed_rate, spread)
                value_diffs.append(abs(swap.value(shocked) - ql_value))
    for name, diffs, desc in (
        ("swap_par_rate", rate_diffs, "Pay-fixed swap par rate (2/5/10y, spread 0 and 25 bp) vs QuantLib VanillaSwap"),
        ("swap_value", value_diffs, "Par swap revalued on shocked curves (-200 to +200 bp) vs QuantLib VanillaSwap"),
    ):
        tolerance, unit = SWAP_TOLERANCES[name]
        measures.append({"measure": name, "description": desc, "instruments": len(diffs),
                         "max_abs_diff": max(diffs), "unit": unit, "tolerance": tolerance})

    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/quantlib_report.py",
        "quantlib_version": ql.__version__,
        "fixture": str(PINNED_FIXTURE.relative_to(REPO_ROOT)),
        "data_date": par.data_date.isoformat(),
        "bond_grid": {
            "coupons": list(COUPONS),
            "maturity_months": list(MATURITY_MONTHS),
            "spreads": list(SPREADS),
            "count": len(BOND_GRID),
        },
        "all_within_tolerance": all(m["max_abs_diff"] < m["tolerance"] for m in measures),
        "quantlib": measures,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"QuantLib {ql.__version__}, data date {par.data_date}, {len(BOND_GRID)} bonds")
    print(f"{'measure':<18} {'n':>4} {'max |diff|':>12} {'tolerance':>10}  unit")
    for m in measures:
        print(f"{m['measure']:<18} {m['instruments']:>4} {m['max_abs_diff']:>12.3e} {m['tolerance']:>10.0e}  {m['unit']}")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0 if report["all_within_tolerance"] else 1


if __name__ == "__main__":
    sys.exit(main())
