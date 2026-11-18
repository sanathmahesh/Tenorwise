"""The ledger: every number the model may state, with its provenance (PLAN.md section 9).

Each value a tool returns gets an ID (v1, v2, ...), a unit, a canonical display
string, a label, and where it came from: tool, arguments, method ID and input
IDs. Tool arguments and fixed descriptors (tenors, shock sizes, hedge ratios,
the 12-month horizon, dates) are context numbers that may be stated untagged.
The ledger lives for one request only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from tenorwise.agent.units import UNITS, display


@dataclass(frozen=True)
class LedgerValue:
    id: str
    value: float
    unit: str
    display: str
    label: str
    tool: str
    args: dict[str, Any]
    method: str
    inputs: list[str]


@dataclass(frozen=True)
class ContextNumber:
    value: float
    unit: str | None
    label: str = ""


@dataclass
class Ledger:
    values: dict[str, LedgerValue] = field(default_factory=dict)
    context: list[ContextNumber] = field(default_factory=list)
    context_dates: set[str] = field(default_factory=set)
    _next: int = 1

    def add(
        self,
        value: float,
        unit: str,
        label: str,
        *,
        tool: str,
        args: dict[str, Any],
        method: str,
        inputs: list[str] | tuple[str, ...] = (),
    ) -> LedgerValue:
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r}")
        vid = f"v{self._next}"
        self._next += 1
        v = LedgerValue(vid, float(value), unit, display(value, unit), label, tool, dict(args), method, list(inputs))
        self.values[vid] = v
        return v

    def add_context(self, value: float, unit: str | None = None, label: str = "") -> None:
        self.context.append(ContextNumber(float(value), unit, label))

    def add_context_date(self, iso: str) -> None:
        """A date may be stated as ISO text or as its parts (day, month, year)."""
        d = date.fromisoformat(iso)
        self.context_dates.add(iso)
        for part in (d.year, d.month, d.day):
            self.add_context(part, None, f"date {iso}")
