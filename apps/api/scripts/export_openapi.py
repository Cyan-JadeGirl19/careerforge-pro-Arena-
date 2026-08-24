"""Export the versioned OpenAPI contract to docs/openapi/v1.json.

Run from anywhere:  python apps/api/scripts/export_openapi.py
CI fails if the committed contract is out of date.
"""
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402

OUT = API_ROOT.parents[1] / "docs" / "openapi" / "v1.json"


def main() -> None:
    spec = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
