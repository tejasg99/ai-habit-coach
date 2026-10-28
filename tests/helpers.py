import json

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def bearer(tokens: dict, key: str = "access_token") -> dict:
    return {"Authorization": f"Bearer {tokens[key]}"}


def valid_plan_text(items_per_day: int = 2) -> str:
    """What a well-behaved LLM would return: 7 days x N items."""
    days = [
        {
            "day": day,
            "items": [
                {
                    "type": "workout" if n == 0 else "meal",
                    "title": f"{day.title()} item {n}",
                    "description": "Easy pace",
                    "target_metric": "30 min" if n == 0 else None,
                }
                for n in range(items_per_day)
            ],
        }
        for day in WEEKDAYS
    ]
    return json.dumps({"days": days})


def today_items(client, headers):
    return client.get("/plan/today", headers=headers).json()["items"]


def log(client, headers, item_id, **extra):
    return client.post("/logs", json={"plan_item_id": item_id, **extra}, headers=headers)
