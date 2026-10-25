import json

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def bearer(tokens: dict, key: str = "access_token") -> dict:
    return {"Authorization": f"Bearer {tokens[key]}"}


def valid_plan_text() -> str:
    """What a well-behaved LLM would return: 7 days x 2 items."""
    days = [
        {
            "day": day,
            "items": [
                {
                    "type": "workout",
                    "title": f"{day.title()} session",
                    "description": "Easy pace",
                    "target_metric": "30 min",
                },
                {
                    "type": "meal",
                    "title": "Balanced meal",
                    "description": "",
                    "target_metric": None,
                },
            ],
        }
        for day in WEEKDAYS
    ]
    return json.dumps({"days": days})
