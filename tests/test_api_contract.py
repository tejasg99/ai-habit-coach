import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def current_contract() -> dict:
    return json.loads(json.dumps(app.openapi()))  # normalise to plain JSON types


def test_the_api_contract_matches_the_committed_snapshot():
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current_contract() == committed, (
        "The API contract changed. If that is intentional, run "
        "`python -m scripts.export_openapi` and commit docs/openapi.json."
    )


def test_every_operation_has_a_unique_readable_id():
    ids = [
        operation["operationId"]
        for path_item in current_contract()["paths"].values()
        for operation in path_item.values()
    ]
    assert len(ids) == len(set(ids))
    assert not any(i.endswith(("_get", "_post", "_put", "_patch", "_delete")) for i in ids)
