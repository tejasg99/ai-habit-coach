from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.enums import PlanStatus
from app.models.plan import Plan, PlanItem
from app.services.llm_client import LLMError, LLMUnavailableError
from app.services.plan_generator import MAX_GENERATIONS_PER_DAY, clean_json_text
from app.services.plans import items_for_weekday, local_today
from tests.helpers import bearer, valid_plan_text

PROFILE = {
    "goal": "build_muscle",
    "fitness_level": "beginner",
    "dietary_pref": "vegetarian",
    "equipment": ["dumbbells"],
    "timezone": "Asia/Kolkata",
    "reminder_time": "19:30:00",
}


class FakeLLM:
    """Stands in for chat_completion. Queue up replies (strings, or exceptions to raise)."""

    def __init__(self):
        self.queue = []
        self.calls = 0

    def __call__(self, messages, **kwargs):
        self.calls += 1
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def fake_llm(monkeypatch):
    fake = FakeLLM()
    # Patch the name where it is USED (plan_generator), not where it is defined.
    monkeypatch.setattr("app.services.plan_generator.chat_completion", fake)
    return fake


@pytest.fixture()
def headers(client, register):
    """Auth headers for a user who has completed onboarding."""
    h = bearer(register())
    assert client.put("/onboarding/me", json=PROFILE, headers=h).status_code == 200
    return h


# ---------- pure functions ----------


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '  {"a": 1}  ',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Here is your plan:\n{"a": 1}\nEnjoy!',
    ],
)
def test_clean_json_text_extracts_the_object(raw):
    assert clean_json_text(raw) == '{"a": 1}'


def test_local_today_uses_the_users_timezone():
    now = datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)  # Saturday 8pm UTC
    assert local_today("UTC", now) == date(2026, 10, 24)
    assert local_today("Asia/Kolkata", now) == date(2026, 10, 25)  # already Sunday in India
    assert local_today("America/Los_Angeles", now) == date(2026, 10, 24)


def test_items_for_weekday_filters_without_a_database():
    plan = Plan(items=[PlanItem(day_of_week=d, title="x") for d in (0, 0, 3)])
    assert len(items_for_weekday(plan, 0)) == 2
    assert len(items_for_weekday(plan, 3)) == 1
    assert items_for_weekday(plan, 6) == []


# ---------- POST /plan/generate ----------


def test_generate_requires_auth(client):
    assert client.post("/plan/generate").status_code == 401


def test_generate_requires_onboarding(client, register, fake_llm):
    res = client.post("/plan/generate", headers=bearer(register()))
    assert res.status_code == 409
    assert fake_llm.calls == 0  # we never paid for a call


def test_generate_saves_and_returns_the_plan(client, headers, fake_llm):
    fake_llm.queue.append(valid_plan_text())
    res = client.post("/plan/generate", headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "active"
    assert len(body["items"]) == 14
    assert {item["day_of_week"] for item in body["items"]} == set(range(7))
    assert "raw_llm_response" not in body and "prompt_version" not in body


def test_fenced_json_is_accepted(client, headers, fake_llm):
    fake_llm.queue.append("```json\n" + valid_plan_text() + "\n```")
    assert client.post("/plan/generate", headers=headers).status_code == 201


def test_invalid_output_is_retried_once(client, headers, fake_llm):
    fake_llm.queue.extend(["not json at all", valid_plan_text()])
    assert client.post("/plan/generate", headers=headers).status_code == 201
    assert fake_llm.calls == 2


def test_persistently_invalid_output_returns_502_and_saves_nothing(client, headers, fake_llm):
    fake_llm.queue.extend(["nope", '{"days": []}'])
    assert client.post("/plan/generate", headers=headers).status_code == 502
    assert fake_llm.calls == 2
    assert client.get("/plan/today", headers=headers).status_code == 404


def test_failed_regeneration_keeps_the_existing_plan(client, headers, fake_llm):
    fake_llm.queue.append(valid_plan_text())
    first = client.post("/plan/generate", headers=headers).json()

    fake_llm.queue.extend(["bad", "bad"])
    assert client.post("/plan/generate", headers=headers).status_code == 502

    today = client.get("/plan/today", headers=headers)
    assert today.status_code == 200
    assert today.json()["plan_id"] == first["id"]  # the old plan is still the active one


def test_llm_unavailable_returns_503_with_retry_after(client, headers, fake_llm):
    fake_llm.queue.append(LLMUnavailableError("down"))
    res = client.post("/plan/generate", headers=headers)
    assert res.status_code == 503
    assert res.headers["retry-after"] == "30"


def test_llm_misconfiguration_returns_502_without_leaking_details(client, headers, fake_llm):
    fake_llm.queue.append(LLMError("HTTP 401 key=super-secret"))
    res = client.post("/plan/generate", headers=headers)
    assert res.status_code == 502
    assert "super-secret" not in res.text


def test_regenerating_archives_the_previous_plan(client, session_factory, headers, fake_llm):
    fake_llm.queue.extend([valid_plan_text(), valid_plan_text()])
    first = client.post("/plan/generate", headers=headers).json()
    second = client.post("/plan/generate", headers=headers).json()
    assert first["id"] != second["id"]

    with session_factory() as db:
        statuses = db.scalars(select(Plan.status).order_by(Plan.id)).all()
    assert statuses == [PlanStatus.archived, PlanStatus.active]
    assert client.get("/plan/today", headers=headers).json()["plan_id"] == second["id"]


def test_daily_generation_limit(client, headers, fake_llm):
    fake_llm.queue.extend([valid_plan_text()] * MAX_GENERATIONS_PER_DAY)
    for _ in range(MAX_GENERATIONS_PER_DAY):
        assert client.post("/plan/generate", headers=headers).status_code == 201
    assert client.post("/plan/generate", headers=headers).status_code == 429
    assert fake_llm.calls == MAX_GENERATIONS_PER_DAY  # the rejected request cost nothing


# ---------- GET /plan/today ----------


def test_today_is_404_without_a_plan(client, headers):
    assert client.get("/plan/today", headers=headers).status_code == 404


def test_today_returns_only_todays_weekday(client, headers, fake_llm, monkeypatch):
    fake_llm.queue.append(valid_plan_text())
    client.post("/plan/generate", headers=headers)
    monkeypatch.setattr("app.services.plans.local_today", lambda tz, now=None: date(2026, 10, 24))

    body = client.get("/plan/today", headers=headers).json()
    assert body["local_date"] == "2026-10-24"
    assert body["weekday"] == 5  # Saturday
    assert len(body["items"]) == 2
    assert {item["day_of_week"] for item in body["items"]} == {5}


def test_users_cannot_see_each_others_plans(client, headers, fake_llm, register):
    fake_llm.queue.append(valid_plan_text())
    client.post("/plan/generate", headers=headers)
    other = bearer(register("bob@example.com"))
    assert client.get("/plan/today", headers=other).status_code == 404
