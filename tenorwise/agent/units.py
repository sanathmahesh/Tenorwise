"""Units and canonical display strings for ledger values.

Units: usd (US dollars), usd_per_bp (DV01), pct (percent), bp (basis points),
years, months, price (per 100 of face), number (dimensionless).
The display string is what the model is told to copy, e.g. "-$412.3M".
"""

from __future__ import annotations

UNITS = ("usd", "usd_per_bp", "pct", "bp", "years", "months", "price", "number")


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1e9:
        return f"{sign}${a / 1e9:,.2f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:,.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:,.1f}K"
    return f"{sign}${a:,.2f}"


def display(value: float, unit: str) -> str:
    x = 0.0 if value == 0 else float(value)  # no negative zero
    if unit == "usd":
        out = _money(x)
    elif unit == "usd_per_bp":
        out = f"{_money(x)} per bp"
    elif unit == "pct":
        out = f"{x:.2f}%"
    elif unit == "bp":
        out = f"{x:.0f} bp" if abs(x - round(x)) < 1e-9 else f"{x:.1f} bp"
    elif unit == "years":
        out = f"{x:.2f} years"
    elif unit == "months":
        out = f"{x:.0f} months"
    elif unit in ("price", "number"):
        out = f"{x:.2f}"
    else:
        raise ValueError(f"unknown unit {unit!r}")
    return out.replace("-0.00", "0.00") if out.startswith("-0.00") else out
