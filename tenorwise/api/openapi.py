"""One OpenAPI document for the API *and* the static snapshot files.

FastAPI only describes models used by routes. The frontend also reads the
snapshot JSON files, so their models are merged into components.schemas, and
the TypeScript types are generated from this one document
(docs/api/openapi.json -> web/src/api/schema.d.ts).
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic.json_schema import models_json_schema

from tenorwise.api.app import app
from tenorwise.snapshot.models import MODELS

SNAPSHOT_MODELS = [model for name, model in MODELS.items() if name != "inputs.json"]  # inputs.json is never served


def build_openapi() -> dict[str, Any]:
    doc = copy.deepcopy(app.openapi())
    _, defs = models_json_schema(
        [(model, "serialization") for model in SNAPSHOT_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    schemas = doc.setdefault("components", {}).setdefault("schemas", {})
    for name, schema in defs.get("$defs", {}).items():
        schemas.setdefault(name, schema)
    return doc
