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
from tests.benchmark.quantlib_curve import quantlib_zero_rates  # noqa: E402
from tests.grids import BOND_GRID, COUPONS, MATURITY_MONTHS, SPREADS  # noqa: E402

OUT = REPO_ROOT / "docs" / "evidence" / "quantlib_report.json"
CURVE_TOLERANCE = 1e-10  # same as tests/benchmark/test_curve_quantlib.py


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
