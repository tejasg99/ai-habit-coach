"""Write the API's OpenAPI document to docs/openapi.json: the contract the mobile app builds against."""

import json
from pathlib import Path

from app.main import app

TARGET = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def main() -> None:
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
