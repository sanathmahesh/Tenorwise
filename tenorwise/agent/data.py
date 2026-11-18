"""What the agent's tools read: the build's snapshot files, loaded per request (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tenorwise.snapshot.store import snapshot_dir

FILES = ("meta", "curve", "portfolio", "mbs", "scenarios", "hedges", "methods", "inputs")


@dataclass(frozen=True)
class AgentData:
    meta: dict[str, Any]
    curve: dict[str, Any]
    portfolio: dict[str, Any]
    mbs: dict[str, Any]
    scenarios: dict[str, Any]
    hedges: dict[str, Any]
    methods: dict[str, Any]
    inputs: dict[str, Any]

    @property
    def data_date(self) -> str:
        return self.meta["data_date"]

    @classmethod
    def load(cls, directory: Path | None = None) -> AgentData | None:
        d = Path(directory) if directory else snapshot_dir()
        loaded = {}
        for name in FILES:
            path = d / f"{name}.json"
            if not path.exists():
                return None
            loaded[name] = json.loads(path.read_text(encoding="utf-8"))
        return cls(**loaded)
