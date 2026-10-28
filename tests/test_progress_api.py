from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event, select

from app.models.plan import Plan
from tests.helpers import bearer, log, today_items, valid_plan_text

THURSDAY, FRIDAY, SATURDAY = date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24)

# The app uses real "now" when it saves generated_at, but these tests pretend it is October 2026,
# so they backdate plans by hand. Any test that depends on time must control EVERY clock.
PLAN_START = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)  # 11:30 on Oct 22 in Kolkata
FRIDAY_NOON = datetime(2026, 10, 23, 6, 30, tzinfo=timezone.utc)  # 12:00 on Oct 23 in Kolkata


@pytest.fixture()
def set_plan_time(session_factory):
    def _set(moment, which=0):
        with session_factory() as db:
            plans = db.scalars(select(Plan).order_by(Plan.id)).all()
            plans[which].generated_at = moment
            db.commit()

    return _set


def progress(client, headers, days=7):
    return client.get("/progress", params={"days": days}, headers=headers)


def by_day(response):
    return {d["day"]: d for d in response.json()["days"]}


def test_progress_requires_auth(client):
    assert client.get("/progress").status_code == 401


@pytest.mark.parametrize("days", [0, -1, 91, "abc"])
def test_days_outside_the_allowed_range_are_rejected(client, headers, days):
    assert progress(client, headers, days).status_code == 422


@pytest.mark.parametrize("days", [1, 90])
def test_days_boundaries_are_accepted(client, headers, set_today, days):
    set_today(SATURDAY)
    res = progress(client, headers, days)
    assert res.status_code == 200
    assert len(res.json()["days"]) == days


def test_progress_without_a_plan(client, headers, set_today):
    set_today(SATURDAY)
    body = progress(client, headers, days=3).json()
    assert [d["day"] for d in body["days"]] == ["2026-10-22", "2026-10-23", "2026-10-24"]
    assert all(d["planned"] == 0 and d["completion_rate"] is None for d in body["days"])
    assert body["total_completed"] == 0 and body["streak"]["current_streak"] == 0


def test_progress_reflects_logged_days(client, headers, plan, set_plan_time, set_today):
    set_plan_time(PLAN_START)

    set_today(THURSDAY)
    for item in today_items(client, headers):  # 2 of 2
        log(client, headers, item["id"])
    set_today(FRIDAY)
    log(client, headers, today_items(client, headers)[0]["id"])  # 1 of 2
    set_today(SATURDAY)  # nothing logged yet today

    res = progress(client, headers, days=4)  # Oct 21 .. Oct 24
    days = by_day(res)
    assert (days["2026-10-21"]["planned"], days["2026-10-21"]["completion_rate"]) == (0, None)
    assert [days["2026-10-22"][k] for k in ("planned", "completed", "completion_rate")] == [
        2,
        2,
        1.0,
    ]
    assert [days["2026-10-23"][k] for k in ("planned", "completed", "completion_rate")] == [
        2,
        1,
        0.5,
    ]
    assert [days["2026-10-24"][k] for k in ("planned", "completed", "completion_rate")] == [
        2,
        0,
        0.0,
    ]

    body = res.json()
    assert (body["total_completed"], body["active_days"]) == (3, 2)
    assert body["streak"]["current_streak"] == 2


def test_regenerating_does_not_rewrite_history(
    client, headers, plan, fake_llm, set_plan_time, set_today
):
    set_today(THURSDAY)
    log(client, headers, today_items(client, headers)[0]["id"])  # 1 of 2, under the first plan

    set_today(FRIDAY)
    fake_llm.queue.append(valid_plan_text(items_per_day=3))
    assert client.post("/plan/generate", headers=headers).status_code == 201
    log(client, headers, today_items(client, headers)[0]["id"])  # 1 of 3, under the new plan

    set_plan_time(PLAN_START, which=0)
    set_plan_time(FRIDAY_NOON, which=1)
    set_today(SATURDAY)

    days = by_day(progress(client, headers, days=3))
    assert (days["2026-10-22"]["planned"], days["2026-10-22"]["completion_rate"]) == (2, 0.5)
    assert (days["2026-10-23"]["planned"], days["2026-10-23"]["completion_rate"]) == (3, 0.333)
    assert days["2026-10-24"]["planned"] == 3


def test_plan_effective_date_uses_the_users_timezone(
    client, headers, plan, set_plan_time, set_today
):
    # 20:00 UTC on Oct 23 is already 01:30 on Oct 24 in Kolkata, so the plan starts on the 24th.
    set_plan_time(datetime(2026, 10, 23, 20, 0, tzinfo=timezone.utc))
    set_today(SATURDAY)
    days = by_day(progress(client, headers, days=2))
    assert days["2026-10-23"]["planned"] == 0
    assert days["2026-10-24"]["planned"] == 2


def test_progress_is_private_and_works_without_a_profile(
    client, headers, plan, set_plan_time, set_today, register
):
    set_plan_time(PLAN_START)
    set_today(THURSDAY)
    log(client, headers, today_items(client, headers)[0]["id"])

    bob = bearer(
        register("bob@example.com")
    )  # no onboarding, so no profile: timezone defaults to UTC
    body = progress(client, bob, days=3).json()
    assert body["total_completed"] == 0
    assert all(d["planned"] == 0 for d in body["days"])


def test_query_count_does_not_depend_on_the_window_size(client, engine, headers, plan, set_today):
    set_today(SATURDAY)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        progress(client, headers, days=1)
        short = len(statements)
        statements.clear()
        progress(client, headers, days=90)
        long = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert short > 0
    assert short == long  # no per-day queries, ever
