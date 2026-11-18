"""Write the browser smoke tests' fixtures to web/e2e/fixtures/ (Phase 11).

    uv run python scripts/make_web_fixtures.py

Everything is produced by the real code, nothing is typed by hand:
  - data/: a full snapshot built from the pinned market fixtures, with the eval
    summary published and LLM_MODEL set, so every screen has real figures;
  - api/: one analyst response per state, made by running the real agent loop
    and verifier with a scripted fake model over the pinned snapshot, and one
    custom scenario priced by the engine.
Timings and request IDs are zeroed so the files are reproducible. A test fails
if the committed files differ from what this script writes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.agent.data import AgentData  # noqa: E402
from tenorwise.agent.loop import run_agent  # noqa: E402
from tenorwise.agent.provider import FakeProvider, ProviderError, tool_response  # noqa: E402
from tenorwise.api.scenario import custom_from_inputs  # noqa: E402
from tenorwise.curve.fixture import load_fixture  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402
from tenorwise.snapshot.build import EVAL_SUMMARY, SNAPSHOT_FILES, compute_snapshot  # noqa: E402
from tenorwise.snapshot.inputs import MarketInputs  # noqa: E402
from tenorwise.snapshot.models import ScenarioRequest  # noqa: E402
from tenorwise.snapshot.serialize import dumps  # noqa: E402

OUT = REPO_ROOT / "web" / "e2e" / "fixtures"
PRODUCTION_MODEL = "zai-org/GLM-5.3"  # the owner's choice (D-075)
FAKE_MODEL = "fixture/scripted-fake"
HEADINGS = ["Positioning", "Rate sensitivity", "Scenario results", "Hedging trade-off", "Caveats"]


def _values(messages) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in messages:
        if m["role"] == "tool":
            body = json.loads(m["content"])
            for v in body.get("values", []):
                out.setdefault(v["label"], v)  # first occurrence wins
    return out


def _cite(v: dict) -> str:
    return f"{v['display']}[[{v['id']}]]"


def _answer(messages):
    v = _values(messages)
    text = (
        f"If every Treasury yield rises 100 bp, the portfolio's market value changes by "
        f"{_cite(v['Change in market value, total'])}, out of {_cite(v['Portfolio market value'])}. "
        f"Of that, {_cite(v['AOCI impact (AFS change, pre-tax)'])} is on available-for-sale securities and "
        f"would reduce AOCI; {_cite(v['HTM change, not recognized'])} is held to maturity and not recognized."
    )
    return tool_response("submit_answer", {"status": "answered", "answer_md": text})


def _wrong(messages):
    v = _values(messages)
    return tool_response("submit_answer", {
        "status": "answered",
        "answer_md": f"The book is worth $1.11B[[{v['Portfolio market value']['id']}]].",
    })


def _commentary(messages):
    v = _values(messages)
    bodies = {
        "Positioning": f"The model book is worth {_cite(v['Portfolio market value'])} with an effective duration of "
                       f"{_cite(v['Portfolio effective duration'])}.",
        "Rate sensitivity": f"It loses {_cite(v['Portfolio DV01'])} for each basis point that rates rise.",
        "Scenario results": f"A 100 bp parallel rise changes its value by {_cite(v['Change in market value, total'])}, "
                            f"of which {_cite(v['AOCI impact (AFS change, pre-tax)'])} would reach AOCI.",
        "Hedging trade-off": f"The full DV01 hedge leaves AOCI net of hedges at "
                             f"{_cite(v['Full DV01 hedge: AOCI net of hedges'])} in that scenario.",
        "Caveats": "Agency mortgage bonds are stylized and IG corporates are a proxy. This is not investment advice.",
    }
    return tool_response("submit_commentary", {"sections": [{"heading": h, "body_md": bodies[h]} for h in HEADINGS]})


def _normalize(response) -> dict:
    body = json.loads(response.model_dump_json())
    body["usage"]["latency_ms"] = 0
    for t in body["trace"]:
        t["ms"] = 0
    body["request_id"] = None
    return body


def agent_fixtures(data: AgentData) -> dict[str, dict]:
    gather = [tool_response("get_portfolio_summary", {}), tool_response("run_scenario", {"scenario_id": "parallel_up_100"})]
    cases = {
        "ask-answered": ("ask", "How much does the portfolio lose if rates rise 100 bp?", gather + [_answer]),
        "ask-cannot-answer": ("ask", "Where will the 10-year yield be next year?", [tool_response(
            "submit_answer", {"status": "cannot_answer",
                              "answer_md": "Tenorwise cannot forecast rates. It shows what happens under the scenarios it prices."})]),
        "ask-blocked": ("ask", "How big is the book?", [tool_response("get_portfolio_summary", {}), _wrong, _wrong]),
        "ask-error": ("ask", "How big is the book?", [ProviderError("model call timed out")]),
        "commentary": ("commentary", None, gather + [tool_response("compare_hedges", {"scenario_id": "parallel_up_100"}),
                                                     _commentary]),
    }
    out = {}
    for name, (mode, question, script) in cases.items():
        r = run_agent(mode, question, [], FakeProvider(list(script), model=FAKE_MODEL), data)
        expected = {"ask-answered": "answered", "ask-cannot-answer": "cannot_answer", "ask-blocked": "blocked",
                    "ask-error": "error", "commentary": "answered"}[name]
        assert r.status == expected, (name, r.status, r.error, [c.reason for c in r.checks if not c.passed])
        out[name] = _normalize(r)
    return out


def render() -> dict[str, str]:
    """{relative path: file text} for every fixture."""
    files: dict[str, str] = {}
    snapshot = compute_snapshot(MarketInputs.from_fixtures(), load_fixture().fetched_at, "fixture",
                                PRODUCTION_MODEL, eval_summary=EVAL_SUMMARY)
    for name in SNAPSHOT_FILES:
        files[f"data/{name}"] = snapshot[name]
    data = AgentData.load(FIXTURES_DIR / "snapshot_v1")
    for name, body in agent_fixtures(data).items():
        files[f"api/{name}.json"] = dumps(body)
    scenario = custom_from_inputs(ScenarioRequest(parallel_bp=50), data.inputs)
    files["api/scenario-parallel-50.json"] = dumps(scenario)
    return files


def main() -> int:
    for rel, text in render().items():
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(render())} files to {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
