"""BNY's investment securities (10-Q, quarter ended 30 Sept 2026) and the sector mapping.

The model portfolio's mix copies BNY's, mapped into four model sectors
(PLAN.md section 6). Weights use the carrying amounts BNY reports in Note 2:
available-for-sale (AFS) at fair value, held-to-maturity (HTM) at amortized
cost.

Plain English: AFS securities can be sold, so they are marked to market and
their gains and losses flow into AOCI ("accumulated other comprehensive
income", part of shareholders' equity). HTM securities are held to maturity,
so they stay at amortized cost and price moves do not hit equity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tenorwise.paths import DATA_DIR

BNY_SOURCE = DATA_DIR / "sources" / "bny_10q_3q26_investment_securities.json"

SECTORS: tuple[str, ...] = ("treasuries", "agency_mbs", "agency_debt", "ig_corporates")
SECTOR_NAMES = {
    "treasuries": "Treasuries",
    "agency_mbs": "Agency mortgage bonds",
    "agency_debt": "Agency debt",
    "ig_corporates": "IG corporates (proxy)",
}
CLASSES: tuple[str, ...] = ("AFS", "HTM")

# PLAN.md section 6, Portfolio.
SECTOR_MAPPING: dict[str, tuple[str, ...]] = {
    "treasuries": ("US Treasury",),
    "agency_mbs": ("Agency RMBS",),
    "agency_debt": ("US government agencies", "Agency commercial MBS"),
    "ig_corporates": (
        "Foreign covered bonds",
        "Non-agency commercial MBS",
        "Non-agency RMBS",
        "Other ABS",
        "Other debt securities",
    ),
}
# Excluded: non-US government needs foreign curves; CLOs are floating rate.
EXCLUDED_LINES: tuple[str, ...] = ("Non-US government", "CLOs")

_AC, _FV = 0, 3


def load_bny_source(path: Path = BNY_SOURCE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mapped_amounts(src: dict[str, Any]) -> dict[tuple[str, str], int]:
    """$ millions per (sector, class): AFS at fair value, HTM at amortized cost."""
    n2 = src["note2_investment_securities"]
    out: dict[tuple[str, str], int] = {}
    for sector, lines in SECTOR_MAPPING.items():
        out[(sector, "AFS")] = sum(n2["available_for_sale"].get(line, [0, 0, 0, 0])[_FV] for line in lines)
        out[(sector, "HTM")] = sum(n2["held_to_maturity"].get(line, [0, 0, 0, 0])[_AC] for line in lines)
    return out


def mapping_weights(src: dict[str, Any]) -> dict[tuple[str, str], float]:
    amounts = mapped_amounts(src)
    total = sum(amounts.values())
    return {key: value / total for key, value in amounts.items()}
