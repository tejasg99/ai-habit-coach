from datetime import date

import pytest
from sqlalchemy import func, select

from app.models.log import Log
from app.models.plan import Plan, PlanItem
from app.services import logs as logs_service
from tests.helpers import bearer, valid_plan_text

SATURDAY = date(2026, 10, 24)  # weekday 5
SUNDAY = date(2026, 10, 25)  # weekday 6
MONDAY = date(2026, 10, 26)  # weekday 0


@pytest.fixture()
def plan(client, headers, fake_llm):
    """The user has a generated plan: 7 days x 2 items."""
    fake_llm.queue.append(valid_plan_text())
    assert client.post("/plan/generate", headers=headers).status_code == 201


def today_items(client, headers):
    return client.get("/plan/today", headers=headers).json()["items"]


def log(client, headers, item_id, **extra):
    return client.post("/logs", json={"plan_item_id": item_id, **extra}, headers=headers)


def streak(client, headers):
    return client.get("/progress/streak", headers=headers).json()


# ---------- logging ----------


def test_log_requires_auth(client):
    assert client.post("/logs", json={"plan_item_id": 1}).status_code == 401


def test_logging_an_item_marks_it_complete(client, headers, plan, set_today):
    set_today(SATURDAY)
    item = today_items(client, headers)[0]
    assert item["completed"] is False

    res = log(client, headers, item["id"], value=42.5)
    assert res.status_code == 201
    assert res.json()["log_date"] == "2026-10-24"
    assert res.json()["value"] == 42.5

    after = today_items(client, headers)[0]
    assert after["completed"] is True
    assert after["log_id"] == res.json()["id"]


def test_logging_twice_is_idempotent(client, session_factory, headers, plan, set_today):
    set_today(SATURDAY)
    item_id = today_items(client, headers)[0]["id"]
    first = log(client, headers, item_id)
    second = log(client, headers, item_id)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Log)) == 1


def test_a_duplicate_that_races_past_the_check_is_handled(
    client, headers, plan, set_today, monkeypatch
):
    set_today(SATURDAY)
    item_id = today_items(client, headers)[0]["id"]
    first = log(client, headers, item_id)
    assert first.status_code == 201

    # Simulate the race: the pre-check "doesn't see" the existing row the first time, so the
    # INSERT runs and the database's unique constraint is what stops it.
    real_find = logs_service._find_log
    calls = {"n": 0}

    def blind_the_first_time(*args, **kwargs):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(*args, **kwargs)

    monkeypatch.setattr("app.services.logs._find_log", blind_the_first_time)

    second = log(client, headers, item_id)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert calls["n"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"plan_item_id": 0},
        {"plan_item_id": -1},
        {"plan_item_id": 1, "value": -5},
        {"plan_item_id": 1, "value": 1e9},
        {"plan_item_id": 1, "log_date": "2020-01-01"},  # the client may not choose the date
    ],
)
def test_invalid_log_payloads_are_rejected(client, headers, payload):
    assert client.post("/logs", json=payload, headers=headers).status_code == 422


# ---------- ownership and rules ----------


def test_item_scheduled_for_another_day_is_rejected(client, headers, plan, set_today):
    set_today(SATURDAY)
    week = client.get("/plan/week", headers=headers).json()["items"]
    monday_item = next(i for i in week if i["day_of_week"] == 0)
    assert log(client, headers, monday_item["id"]).status_code == 409


def test_unknown_item_is_404(client, headers, plan, set_today):
    set_today(SATURDAY)
    assert log(client, headers, 99999).status_code == 404


def test_cannot_log_someone_elses_item(client, headers, plan, set_today, register):
    set_today(SATURDAY)
    alices_item = today_items(client, headers)[0]["id"]
    bob = bearer(register("bob@example.com"))
    assert log(client, bob, alices_item).status_code == 404  # same answer as "doesn't exist"


def test_items_from_an_archived_plan_cannot_be_logged(client, headers, plan, fake_llm, set_today):
    set_today(SATURDAY)
    old_item = today_items(client, headers)[0]["id"]
    fake_llm.queue.append(valid_plan_text())
    assert client.post("/plan/generate", headers=headers).status_code == 201
    assert log(client, headers, old_item).status_code == 404


# ---------- streaks ----------


def test_streak_endpoint_requires_auth(client):
    assert client.get("/progress/streak").status_code == 401


def test_new_user_has_no_streak(client, headers):
    assert streak(client, headers) == {
        "current_streak": 0,
        "longest_streak": 0,
        "last_completed_date": None,
        "completed_today": False,
    }


def test_first_log_starts_a_streak(client, headers, plan, set_today):
    set_today(SATURDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    assert streak(client, headers) == {
        "current_streak": 1,
        "longest_streak": 1,
        "last_completed_date": "2026-10-24",
        "completed_today": True,
    }


def test_more_logs_on_the_same_day_do_not_extend_the_streak(client, headers, plan, set_today):
    set_today(SATURDAY)
    for item in today_items(client, headers):
        assert log(client, headers, item["id"]).status_code == 201
    assert streak(client, headers)["current_streak"] == 1


def test_consecutive_days_extend_the_streak(client, headers, plan, set_today):
    set_today(SATURDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    set_today(SUNDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    s = streak(client, headers)
    assert (s["current_streak"], s["longest_streak"]) == (2, 2)


def test_streak_survives_until_the_day_ends(client, headers, plan, set_today):
    set_today(SATURDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    set_today(SUNDAY)  # a new day, nothing logged yet
    s = streak(client, headers)
    assert s["current_streak"] == 1
    assert s["completed_today"] is False


def test_a_missed_day_resets_the_streak(client, headers, plan, set_today):
    set_today(SATURDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    set_today(MONDAY)  # Sunday was skipped
    assert streak(client, headers)["current_streak"] == 0  # a stale streak reads as 0

    log(client, headers, today_items(client, headers)[0]["id"])
    s = streak(client, headers)
    assert (s["current_streak"], s["longest_streak"]) == (1, 1)


# ---------- undo and cleanup ----------


def test_deleting_a_log_undoes_the_completion_and_the_streak(client, headers, plan, set_today):
    set_today(SATURDAY)
    log_id = log(client, headers, today_items(client, headers)[0]["id"]).json()["id"]

    assert client.delete(f"/logs/{log_id}", headers=headers).status_code == 204
    assert today_items(client, headers)[0]["completed"] is False
    s = streak(client, headers)
    assert s["current_streak"] == 0 and s["completed_today"] is False
    assert client.delete(f"/logs/{log_id}", headers=headers).status_code == 404


def test_cannot_delete_someone_elses_log(client, headers, plan, set_today, register):
    set_today(SATURDAY)
    log_id = log(client, headers, today_items(client, headers)[0]["id"]).json()["id"]
    bob = bearer(register("bob@example.com"))
    assert client.delete(f"/logs/{log_id}", headers=bob).status_code == 404
    assert today_items(client, headers)[0]["completed"] is True


def test_deleting_the_account_removes_plans_and_logs(
    client, session_factory, headers, plan, set_today
):
    set_today(SATURDAY)
    log(client, headers, today_items(client, headers)[0]["id"])
    assert client.delete("/users/me", headers=headers).status_code == 204
    with session_factory() as db:
        for model in (Log, PlanItem, Plan):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_cannot_delete_a_log_from_a_previous_day(client, headers, plan, set_today):
    set_today(SATURDAY)
    log_id = log(client, headers, today_items(client, headers)[0]["id"]).json()["id"]
    set_today(SUNDAY)
    assert client.delete(f"/logs/{log_id}", headers=headers).status_code == 409
    s = streak(client, headers)
    assert s["current_streak"] == 1 and s["last_completed_date"] == "2026-10-24"


def test_ownership_is_checked_before_the_date_rule(client, headers, plan, set_today, register):
    set_today(SATURDAY)
    log_id = log(client, headers, today_items(client, headers)[0]["id"]).json()["id"]
    set_today(SUNDAY)
    bob = bearer(register("bob@example.com"))
    assert client.delete(f"/logs/{log_id}", headers=bob).status_code == 404  # not 409
