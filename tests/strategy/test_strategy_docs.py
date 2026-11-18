"""Strategy artifacts (PLAN.md section 11, Phase 10).

The plan's test: every number in the model memo traces to an eval results file.
"Traces" uses the analyst's own number parser and verification rule: each
number printed in the memo must be some value from the eval results, correctly
rounded to the printed precision. The same check covers the risk and control
table, against the eval results and the QuantLib report. Document identifiers
(SR 26-2, NIST AI 600-1, section numbers, decision and assumption IDs), written
dates of sources, links and code spans are not figures and are removed first.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.doc_numbers import QUANTLIB, eval_ledger, quantlib_values, untraced

REPO = Path(__file__).resolve().parents[2]
STRATEGY = REPO / "docs" / "strategy"
EVALS = REPO / "docs" / "evidence" / "evals"
EFFORT_COLUMNS = ["task_id", "method", "date", "start_time", "end_time", "completed", "matches_engine", "notes"]

def read(name: str) -> str:
    return (STRATEGY / name).read_text(encoding="utf-8")


# ------------------------------------------------------------------ files


@pytest.mark.parametrize("name", ["opportunity-map.md", "effort.md", "effort-timings.csv", "model-memo.md",
                                  "risk-controls.md", "rollout-plan.md", "decision-log.md"])
def test_strategy_file_exists(name):
    assert (STRATEGY / name).is_file()


# ------------------------------------------------------------------ model memo


def test_every_number_in_the_model_memo_traces_to_an_eval_results_file():
    led, dates = eval_ledger()
    assert untraced(read("model-memo.md"), led, dates) == []


def test_the_trace_check_catches_an_invented_number():
    led, dates = eval_ledger()
    assert untraced("Accuracy was 97.3% at $0.0031 per question.", led, dates) == ["97.3%", "$0.0031"]


def test_the_model_memo_covers_every_model_tested_and_makes_a_recommendation():
    memo = read("model-memo.md")
    for m in json.loads((EVALS / "summary.json").read_text())["models"]:
        assert f"`{m['id']}`" in memo
    assert "## Recommendation" in memo and "trade-off" in memo.lower()


# ------------------------------------------------------------------ risk and control table


def test_every_number_in_the_risk_table_traces_to_eval_or_quantlib_results():
    led, dates = eval_ledger()
    quantlib_values(led)
    dates.add(json.loads(QUANTLIB.read_text())["generated_at"][:10])
    assert untraced(read("risk-controls.md"), led, dates) == []


def test_every_test_named_as_evidence_exists():
    text = read("risk-controls.md") + read("rollout-plan.md")
    named = re.findall(r"`(tests/[\w/]+\.py)::(\w+)`", text)
    assert named, "the risk table must name tests as evidence"
    for path, name in named:
        source = (REPO / path).read_text()
        assert re.search(rf"^def {name}\b", source, re.M), f"{path}::{name} does not exist"


def test_risk_table_states_scope_and_claims_no_validation():
    text = read("risk-controls.md")
    assert "footnote 3" in text.lower()
    assert "NIST AI 600-1" in text
    lowered = text.lower()
    assert "not been validated" in lowered and "does not claim compliance" in lowered
    for term in ("model materiality", "effective challenge", "conceptual soundness", "outcomes analysis",
                 "ongoing model monitoring", "model inventory", "model limitations", "third-party"):
        assert term in lowered, term


# ------------------------------------------------------------------ opportunity map


SUMMARY_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([1-5])\s*\|\s*([1-5])\s*\|\s*([1-5])\s*\|", re.M)


def test_opportunity_map_scores_8_to_10_workflows_with_a_reason_per_score():
    text = read("opportunity-map.md")
    rows = SUMMARY_ROW.findall(text)
    assert 8 <= len(rows) <= 10
    for n, name, _team, value, feasibility, risk in rows:
        section = re.search(rf"^### {n}\. (.+?)$(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
        assert section, f"no section for workflow {n}"
        assert section.group(1).strip() == name.strip()
        body = section.group(2)
        for label, score in (("Value", value), ("Feasibility", feasibility), ("Risk", risk)):
            m = re.search(rf"^- \*\*{label} {score}\.\*\* \S.{{20,}}", body, re.M)
            assert m, f"workflow {n}: no reason for {label} {score}"


def test_opportunity_map_says_scores_are_judgments_and_explains_the_choice():
    text = read("opportunity-map.md")
    assert "reasoned judgments from public sources, not measurements or practitioner interviews" in text
    assert "## Rubric" in text and "## Why this use case" in text and "## Sources" in text


# ------------------------------------------------------------------ effort


def test_effort_timings_csv_has_the_agreed_columns_and_only_recorded_rows():
    with (STRATEGY / "effort-timings.csv").open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == EFFORT_COLUMNS
    tasks = set(re.findall(r"^### (T\d)\.", read("effort.md"), re.M))
    for r in rows[1:]:
        assert r[0] in tasks and r[1] in ("manual", "tool"), r


def test_effort_sheet_names_the_operator_and_the_tasks():
    text = read("effort.md")
    assert "one non-expert" in text
    assert len(re.findall(r"^### T\d\.", text, re.M)) >= 4


# ------------------------------------------------------------------ rollout plan


def test_rollout_plan_is_marked_as_an_unexecuted_proposal():
    text = read("rollout-plan.md")
    assert "proposal" in text.lower() and "has not been executed" in text
    for heading in ("## Pilot group", "## Human review", "## What is logged", "## Rollback triggers"):
        assert heading in text, heading


# ------------------------------------------------------------------ the About page (vitest)


def test_about_page_component_tests_pass():
    web = REPO / "web"
    if not (web / "node_modules").exists():
        pytest.fail("web/node_modules missing: run `npm ci --prefix web` first")
    r = subprocess.run(["npm", "test", "--prefix", str(web)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
