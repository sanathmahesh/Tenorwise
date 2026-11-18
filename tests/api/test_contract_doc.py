"""docs/api/contract.md (the design's API contract) must match the code."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_committed_contract_doc_matches_the_models():
    spec = importlib.util.spec_from_file_location("export_contract", REPO / "scripts" / "export_contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    committed = (REPO / "docs" / "api" / "contract.md").read_text(encoding="utf-8")
    assert committed == mod.render(), "run: uv run python scripts/export_contract.py"


def test_contract_doc_lists_the_phase_11_additions():
    text = (REPO / "docs" / "api" / "contract.md").read_text(encoding="utf-8")
    assert "`market_value_by_class`" in text and "`incentive_pct`" in text
