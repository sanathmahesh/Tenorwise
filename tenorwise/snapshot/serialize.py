"""Deterministic JSON (PLAN.md section 8): sorted keys, fixed rounding, no negative zero.

Every float in the published snapshot and API responses is rounded to 10
significant figures. Money is in US dollars there, so 10 significant figures
keeps dollar precision on a $10B book.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

SIGNIFICANT_FIGURES = 10


def round_floats(obj: Any) -> Any:
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        x = float(f"{obj:.{SIGNIFICANT_FIGURES}g}")
        return 0.0 if x == 0 else x  # no negative zero
    if isinstance(obj, dict):
        return {k: round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v) for v in obj]
    raise TypeError(f"cannot serialize {type(obj).__name__}")


def to_jsonable(model: BaseModel) -> Any:
    """Contract field names (aliases), JSON types, rounded floats."""
    return round_floats(model.model_dump(by_alias=True, mode="json"))


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def dumps_exact(model: BaseModel) -> str:
    """Full precision (Python float repr round-trips exactly); still sorted and stable."""
    return dumps(model.model_dump(by_alias=True, mode="json"))
