"""Export the OpenAPI document (API + snapshot models) to docs/api/openapi.json.

    uv run python scripts/export_openapi.py && npm run gen:types --prefix web

The TypeScript types in web/src/api/schema.d.ts are generated from it.
tests/api/test_web_build.py fails if the committed document is out of date.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tenorwise.api.openapi import build_openapi  # noqa: E402

OUT = REPO_ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_openapi(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
