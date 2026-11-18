"""Write docs/api/contract.md: the API contract for the design, generated from the code's own models.

    uv run python scripts/export_contract.py

Field names, nesting and nullability come from the pydantic models; IDs and list
sizes come from the pinned fixture snapshot. A test fails if the committed file
is out of date.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
OUT = REPO_ROOT / "docs" / "api" / "contract.md"

from tenorwise.agent import schemas as a  # noqa: E402
from tenorwise.agent.data import AgentData  # noqa: E402
from tenorwise.paths import FIXTURES_DIR  # noqa: E402
from tenorwise.snapshot import models as m  # noqa: E402

ADDED_NOTE = " *(added beyond PLAN.md section 8)*"
KEY_NAMES = {"methods": "method ID", "results": "model ID", "values": "value tag (v1, v2, ...)"}


def resolve(node, defs):
    while "$ref" in node:
        node = defs[node["$ref"].split("/")[-1]]
    return node


def describe(prop, defs):
    """(type text, child object schema or None, nullable)"""
    nullable = False
    if "anyOf" in prop:
        options = [o for o in prop["anyOf"] if o.get("type") != "null"]
        nullable = len(options) < len(prop["anyOf"])
        prop = {**prop, **options[0]} if len(options) == 1 else prop
    prop = {**prop, **resolve(prop, defs)} if "$ref" in prop else prop
    if "enum" in prop:
        return " | ".join(f'"{v}"' for v in prop["enum"]), None, nullable
    if "const" in prop:
        return f'"{prop["const"]}"', None, nullable
    t = prop.get("type")
    if t == "array":
        item = resolve(prop["items"], defs)
        if item.get("type") == "object" and "properties" in item:
            return "list of objects:", item, nullable
        return f"list of {describe(item, defs)[0]}", None, nullable
    if t == "object" and "properties" in prop:
        return "object:", prop, nullable
    if t == "object":
        extra = prop.get("additionalProperties")
        if isinstance(extra, dict) and extra:
            inner = resolve(extra, defs)
            if inner.get("type") == "object" and "properties" in inner:
                return "map from key to object:", inner, nullable
            return f"map from key to {describe(inner, defs)[0]}", None, nullable
        return "object (free-form)", None, nullable
    return {"number": "number", "integer": "integer", "string": "string", "boolean": "boolean"}.get(t, str(t)), None, nullable


def walk(schema, defs, depth=0, out=None):
    out = [] if out is None else out
    for name, prop in schema.get("properties", {}).items():
        text, child, nullable = describe(prop, defs)
        desc = prop.get("description") or ""
        added = desc.startswith("added")
        desc = desc.removeprefix("added").lstrip(": ").strip()
        if name in KEY_NAMES:
            text = text.replace("map from key", f"map from {KEY_NAMES[name]}")
        line = f"{'  ' * depth}- `{name}`: {text}"
        if nullable:
            line = line.rstrip(":") + " or null" + (":" if line.endswith(":") else "")
        if desc:
            line += f" ({desc})"
        if added:
            line += ADDED_NOTE
        out.append(line)
        if child is not None:
            walk(child, defs, depth + 1, out)
    return out


def model_block(model):
    s = model.model_json_schema(by_alias=True, mode="serialization")
    return "\n".join(walk(s, s.get("$defs", {})))


def render() -> str:
    d = AgentData.load(FIXTURES_DIR / "snapshot_v1")
    ids = {
        "Scenario IDs (in order)": [f'`{s["id"]}` ({s["name"]})' for s in d.scenarios["scenarios"]],
        "Hedge strategy IDs": [f'`{s["id"]}` ({s["name"]})' for s in d.hedges["strategies"]],
        "Sector IDs": [f'`{g["id"]}` ({g["name"]})' for g in d.portfolio["by_sector"]],
        "Accounting class IDs": [f'`{g["id"]}` ({g["name"]})' for g in d.portfolio["by_class"]],
        "Method IDs (methods.json)": [f"`{k}`" for k in d.methods["methods"]],
    }
    sizes = [
        f"curve points: {len(d.curve['points'])} (tenors in years: {', '.join(f'{p['tenor_years']:.4g}' for p in d.curve['points'])})",
        f"positions: {len(d.portfolio['positions'])}",
        f"scenarios: {len(d.scenarios['scenarios'])}; hedge strategies: {len(d.hedges['strategies'])}; "
        f"hedge grid rows: {len(d.hedges['grid'])} (every strategy x every scenario)",
        f"mortgage profile rows: {len(d.mbs['profile'])} (shift_bp from {d.mbs['profile'][0]['shift_bp']:g} to "
        f"{d.mbs['profile'][-1]['shift_bp']:g}); s_curve rows: {len(d.mbs['s_curve'])}",
    ]

    files = [("meta.json", m.Meta), ("curve.json", m.Curve), ("portfolio.json", m.Portfolio), ("mbs.json", m.Mbs),
             ("scenarios.json", m.Scenarios), ("hedges.json", m.Hedges), ("methods.json", m.Methods),
             ("evidence.json", m.Evidence)]
    out = [
        "# Tenorwise API contract",
        "",
        "For the design handoff. Generated from the code's response models by `scripts/export_contract.py`; nothing here is typed by hand.",
        "**Field names are fixed.** If the design needs a field that is not listed, flag it instead of inventing one.",
        f'Fields marked{ADDED_NOTE} were approved additions to the plan\'s list.',
        "",
        "## Units and signs",
        "",
        "- Money is in US dollars, for example `market_value` and `delta_mv`. DV01 is in US dollars per 1 bp.",
        "- Rates and yields are in percent: 4.93 means 4.93%. Shocks, shifts and spreads ending `_bp` are in basis points.",
        "- Durations, maturities and average life are in years. Prices are per 100 of face.",
        "- **A change is after minus before.** A negative `delta_mv`, `aoci_impact` or `htm_unrecognized` is a loss.",
        "- DV01 and duration are positive for an ordinary long bond. A pay-fixed swap's `dv01` is negative.",
        "- In `hedges.grid`:",
        "  - `loss_avoided` is the swaps' gain or loss in that scenario;",
        "  - `carry_given_up` is positive when the hedge costs carry and negative when it adds carry. Negative values occur in the real data.",
        "- In `evidence.json`:",
        "  - `accuracy`, `block_rate` (after the repair attempt) and `verified_but_wrong_rate` are fractions from 0 to 1;",
        "  - latencies are in milliseconds;",
        "  - `cost_per_question_usd` is in US dollars;",
        "  - `runs` is the number of repeats.",
        "- Dates are ISO strings (YYYY-MM-DD).",
        "",
        "## Where the data comes from",
        "",
        "- **Static files.** `GET /data/v1/<file>.json` serves the files below. They are built once per deploy, so the page loads them directly.",
        "- **Custom scenarios.** `POST /api/scenario` computes one on demand. There is no interpolation; the engine prices it.",
        "- **The analyst.** `POST /api/agent/ask` and `POST /api/agent/commentary`.",
        "- **Health.** `GET /api/health`.",
        "",
        "## IDs and list sizes (from the pinned snapshot)",
        "",
    ]
    for title, values in ids.items():
        out.append(f"- **{title}:** " + ", ".join(values))
    out.append("- **Sizes:** " + "; ".join(sizes))
    out += [
        "",
        "Scenario `base` is today's curve with no shock. The other seven are the presets.",
        "",
        "## Static files",
    ]
    for name, model in files:
        out += ["", f"### {name}", "", model_block(model)]
    out += [
        "",
        "## Endpoints",
        "",
        "### GET /api/health",
        "",
        model_block(m.HealthResponse),
        "",
        "### POST /api/scenario",
        "",
        "Request: exactly one of a parallel shift or key-rate shocks. Each is limited to -300 to +300 bp.",
        "",
        model_block(m.ScenarioRequest),
        "",
        'Response: one scenario, shaped like an entry in `scenarios.json` with `id` "custom", plus its hedge grid rows.',
        "",
        model_block(m.ScenarioResponse),
        "",
        "### POST /api/agent/ask and POST /api/agent/commentary",
        "",
        "Ask request (commentary takes an empty object `{}`):",
        "",
        model_block(a.AskRequest),
        "",
        "Response:",
        "",
        model_block(a.AgentResponse),
        "",
        "How the analyst's response is shown:",
        "",
        "- **Number tags.** In `answer_md` and in each `sections[].body_md`, every number is followed by a tag such as `[[v12]]`. The interface hides the tag and makes the number a link that opens `values.v12`: its label, the tool and arguments, the method, and its inputs for derived figures.",
        "- **`answered`:** show `answer_md` for a question, or `sections` for commentary, with `verification_rule` nearby.",
        "- **`cannot_answer`:** show `answer_md`, which explains why the question can't be answered.",
        "- **`blocked`:** no prose. Show `fallback`, a table of raw engine results, and say verification failed. `answer_md` and `sections` are empty.",
        "- **`error`:** show `error`.",
        "- **Commentary:** always show `notice` (\"Draft, requires human review\").",
        "- **HTTP errors** return `{\"detail\": \"...\"}` instead of a response body:",
        "  - 429: daily limit reached (per IP address, or global);",
        "  - 503: AI temporarily unavailable;",
        "  - 422: invalid input, for example an empty question or one over 1,000 characters.",
        "- **Not shown in the interface:** `checks`, `trace` and `usage`. They are available for a details drawer if wanted.",
        "",
        "## Required on screen",
        "",
        "- The market data date: `meta.data_date`.",
        "- \"Stylized\" on the agency mortgage pool, its charts and mortgage positions: `mbs.stylized`, `mbs.stylized_note` and `positions[].stylized`.",
        "- \"Proxy\" on IG corporates: `positions[].proxy_for` and the sector name.",
        "- The portfolio source citation: `portfolio.source.text` and `portfolio.source.url`.",
        "- The mortgage rate attribution: `mbs.mortgage_rate.attribution`.",
        "- The FRED footer: \"This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis. By using Tenorwise you agree to the FRED® API Terms of Use\", with a link to https://fred.stlouisfed.org/docs/api/terms_of_use.html.",
        "- Assumptions: `meta.assumptions`, wherever a result depends on one. For example, the swap spread (`hedges.swap_spread_bp`) is an assumption.",
        "",
        "## Pages rendered from Markdown at build time",
        "",
        "The About page bodies are the repository's `docs/strategy/*.md` files: the opportunity map, effort, model memo, risks and controls, rollout plan and decision log.",
        "- **Styling:** design the styles for generic Markdown: headings, paragraphs, lists, bold, code spans, links and wide tables (which need to scroll on phone).",
        "- **Effort timings:** come from a CSV. Until it has rows, show \"Study not run\" and that time saved has not been measured (D-081).",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
