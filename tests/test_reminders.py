from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.models.profile import Profile
from app.models.push_token import PushToken
from app.models.reminder_send import ReminderSend
from app.services.expo_push import PushError, PushResult, PushUnavailableError
from app.services.reminders import build_reminder, reminder_local_date, run_reminder_sweep
from app.services.streaks import StreakInfo
from tests.helpers import bearer, log, today_items, valid_plan_text

UTC = timezone.utc
KOLKATA, NEW_YORK = "Asia/Kolkata", "America/New_York"


@pytest.mark.parametrize(
    "now, tz, at, expected",
    [
        # window opens exactly at the reminder time and closes 2 hours later (exclusive)
        (datetime(2026, 10, 24, 13, 59, tzinfo=UTC), KOLKATA, time(19, 30), None),
        (datetime(2026, 10, 24, 14, 0, tzinfo=UTC), KOLKATA, time(19, 30), date(2026, 10, 24)),
        (datetime(2026, 10, 24, 15, 59, tzinfo=UTC), KOLKATA, time(19, 30), date(2026, 10, 24)),
        (datetime(2026, 10, 24, 16, 0, tzinfo=UTC), KOLKATA, time(19, 30), None),
        # the returned date is the USER's local date, which can differ from the UTC date
        (datetime(2026, 10, 24, 20, 0, tzinfo=UTC), KOLKATA, time(1, 30), date(2026, 10, 25)),
        # the window is cut off at local midnight
        (datetime(2026, 10, 24, 18, 29, tzinfo=UTC), KOLKATA, time(23, 30), date(2026, 10, 24)),
        (datetime(2026, 10, 24, 18, 40, tzinfo=UTC), KOLKATA, time(23, 30), None),
        # spring forward: 02:30 never exists on 8 March 2026; it fires when the clock jumps to 03:00
        (datetime(2026, 3, 8, 6, 45, tzinfo=UTC), NEW_YORK, time(2, 30), None),
        (datetime(2026, 3, 8, 7, 0, tzinfo=UTC), NEW_YORK, time(2, 30), date(2026, 3, 8)),
        # fall back: 01:30 happens twice on 1 Nov 2026. Both are "due"; the ledger stops a 2nd send
        (datetime(2026, 11, 1, 5, 30, tzinfo=UTC), NEW_YORK, time(1, 30), date(2026, 11, 1)),
        (datetime(2026, 11, 1, 6, 30, tzinfo=UTC), NEW_YORK, time(1, 30), date(2026, 11, 1)),
    ],
)
def test_reminder_window(now, tz, at, expected):
    assert reminder_local_date(now, tz, at) == expected


def test_a_naive_datetime_is_refused():
    with pytest.raises(ValueError):
        reminder_local_date(datetime(2026, 10, 24, 14, 0), KOLKATA, time(19, 30))


@pytest.mark.parametrize(
    "streak, expected_title",
    [
        (0, "Ready for today's plan?"),
        (1, "Ready for today's plan?"),
        (2, "Keep your 2-day streak alive"),
        (30, "Keep your 30-day streak alive"),
    ],
)
def test_message_depends_on_the_streak(streak, expected_title):
    info = StreakInfo(
        current_streak=streak,
        longest_streak=streak,
        last_completed_date=None,
        completed_today=False,
    )
    assert build_reminder(info)[0] == expected_title


SATURDAY, FRIDAY, THURSDAY = date(2026, 10, 24), date(2026, 10, 23), date(2026, 10, 22)
NOW = datetime(2026, 10, 24, 14, 5, tzinfo=UTC)  # Saturday 19:35 in Kolkata

ALICE_TOKEN = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
BOB_TOKEN = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"
ALICE_PROFILE = {
    "goal": "build_muscle",
    "fitness_level": "beginner",
    "dietary_pref": "vegetarian",
    "equipment": ["dumbbells"],
    "timezone": "Asia/Kolkata",
    "reminder_time": "19:30:00",
}
BOB_PROFILE = {**ALICE_PROFILE, "timezone": "America/Los_Angeles", "reminder_time": "19:00:00"}


class FakeSender:
    """Stands in for Expo. Records every call; behaviour is set per test."""

    def __init__(self):
        self.calls = []
        self.fail_with = None  # an exception to raise
        self.statuses = {}  # token -> status override (default "ok")

    def __call__(self, messages):
        self.calls.append(list(messages))
        if self.fail_with is not None:
            raise self.fail_with
        return [PushResult(m.to, self.statuses.get(m.to, "ok")) for m in messages]


@pytest.fixture()
def add_user(client, register, fake_llm):
    """Creates a user with a profile, an active plan and a registered device token."""

    def _add(email, profile, token):
        headers = bearer(register(email))
        assert client.put("/onboarding/me", json=profile, headers=headers).status_code == 200
        fake_llm.queue.append(valid_plan_text())
        assert client.post("/plan/generate", headers=headers).status_code == 201
        res = client.post("/notifications/register-token", json={"token": token}, headers=headers)
        assert res.status_code == 204
        return headers

    return _add


@pytest.fixture()
def alice(add_user):
    return add_user("alice@example.com", ALICE_PROFILE, ALICE_TOKEN)


def sweep(session_factory, sender, now=NOW):
    with session_factory() as db:
        return run_reminder_sweep(db, now, sender)


def count(session_factory, model):
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_a_due_user_with_nothing_logged_gets_one_reminder(session_factory, alice):
    sender = FakeSender()
    stats = sweep(session_factory, sender)
    assert (stats.considered, stats.due, stats.sent) == (1, 1, 1)
    (messages,) = sender.calls
    assert [m.to for m in messages] == [ALICE_TOKEN]
    assert messages[0].title == "Ready for today's plan?"
    assert messages[0].data == {"screen": "today"}
    assert count(session_factory, ReminderSend) == 1


def test_running_the_sweep_twice_sends_once(session_factory, alice):
    sender = FakeSender()
    sweep(session_factory, sender)
    second = sweep(session_factory, sender, NOW + timedelta(minutes=15))
    assert second.skipped == 1 and second.sent == 0
    assert len(sender.calls) == 1


@pytest.mark.parametrize(
    "now",
    [datetime(2026, 10, 24, 13, 59, tzinfo=UTC), datetime(2026, 10, 24, 16, 0, tzinfo=UTC)],
)
def test_nobody_is_reminded_outside_their_window(session_factory, alice, now):
    sender = FakeSender()
    stats = sweep(session_factory, sender, now)
    assert (stats.considered, stats.due) == (1, 0)
    assert sender.calls == []


def test_a_user_who_already_logged_today_is_left_alone(client, session_factory, alice, set_today):
    set_today(SATURDAY)
    log(client, alice, today_items(client, alice)[0]["id"])
    sender = FakeSender()
    stats = sweep(session_factory, sender)
    assert stats.skipped == 1 and sender.calls == []
    assert count(session_factory, ReminderSend) == 0


def test_an_active_streak_changes_the_message(client, session_factory, alice, set_today):
    for day in (THURSDAY, FRIDAY):
        set_today(day)
        log(client, alice, today_items(client, alice)[0]["id"])
    sender = FakeSender()
    sweep(session_factory, sender)  # nothing logged on Saturday yet
    assert sender.calls[0][0].title == "Keep your 2-day streak alive"


def test_users_without_a_device_are_not_considered(client, register, session_factory):
    headers = bearer(register("carol@example.com"))
    client.put("/onboarding/me", json=ALICE_PROFILE, headers=headers)
    sender = FakeSender()
    assert sweep(session_factory, sender).considered == 0


def test_a_user_without_a_plan_is_skipped_and_the_day_is_not_used_up(
    client, register, session_factory
):
    headers = bearer(register("carol@example.com"))
    client.put("/onboarding/me", json=ALICE_PROFILE, headers=headers)
    client.post("/notifications/register-token", json={"token": ALICE_TOKEN}, headers=headers)
    sender = FakeSender()
    stats = sweep(session_factory, sender)
    assert stats.skipped == 1 and sender.calls == []
    assert count(session_factory, ReminderSend) == 0


def test_a_temporary_expo_outage_is_retried_by_the_next_sweep(session_factory, alice):
    sender = FakeSender()
    sender.fail_with = PushUnavailableError("expo down")
    first = sweep(session_factory, sender)
    assert first.released == 1
    assert count(session_factory, ReminderSend) == 0  # the day was given back

    sender.fail_with = None
    second = sweep(session_factory, sender, NOW + timedelta(minutes=15))
    assert second.sent == 1
    assert count(session_factory, ReminderSend) == 1


def test_a_permanent_rejection_is_not_retried(session_factory, alice):
    sender = FakeSender()
    sender.fail_with = PushError("bad credentials")
    assert sweep(session_factory, sender).failed == 1
    sender.fail_with = None
    sweep(session_factory, sender, NOW + timedelta(minutes=15))
    assert len(sender.calls) == 1  # the second sweep never called Expo


def test_dead_tokens_are_pruned(session_factory, alice):
    sender = FakeSender()
    sender.statuses[ALICE_TOKEN] = "invalid_token"
    stats = sweep(session_factory, sender)
    assert (stats.pruned_tokens, stats.failed, stats.sent) == (1, 1, 0)
    assert count(session_factory, PushToken) == 0
    assert count(session_factory, ReminderSend) == 1  # nothing left to retry today


def test_one_dead_token_does_not_stop_the_other_device(client, session_factory, alice):
    second_phone = "ExponentPushToken[dddddddddddddddddddddd]"
    client.post("/notifications/register-token", json={"token": second_phone}, headers=alice)
    sender = FakeSender()
    sender.statuses[ALICE_TOKEN] = "invalid_token"
    stats = sweep(session_factory, sender)
    assert (stats.sent, stats.pruned_tokens) == (1, 1)
    with session_factory() as db:
        assert db.scalars(select(PushToken.token)).all() == [second_phone]


def test_each_user_is_judged_in_their_own_timezone(session_factory, alice, add_user):
    add_user("bob@example.com", BOB_PROFILE, BOB_TOKEN)
    now = datetime(
        2026, 10, 25, 2, 5, tzinfo=UTC
    )  # Alice: 07:35 on the 25th. Bob: 19:05 on the 24th
    sender = FakeSender()
    stats = sweep(session_factory, sender, now)
    assert (stats.considered, stats.due, stats.sent) == (2, 1, 1)
    assert [m.to for m in sender.calls[0]] == [BOB_TOKEN]
    with session_factory() as db:
        assert db.scalar(select(ReminderSend.local_date)) == date(
            2026, 10, 24
        )  # his day, not the UTC date


class ExplodesForAlice(FakeSender):
    def __call__(self, messages):
        if messages[0].to == ALICE_TOKEN:
            raise RuntimeError("boom")
        return super().__call__(messages)


def test_one_users_crash_does_not_stop_everyone_else(session_factory, alice, add_user):
    add_user("bob@example.com", {**BOB_PROFILE, "reminder_time": "07:00:00"}, BOB_TOKEN)
    stats = sweep(session_factory, ExplodesForAlice())  # at NOW both are due
    assert (stats.failed, stats.sent) == (1, 1)


def test_a_corrupt_profile_does_not_stop_the_sweep(session_factory, alice, add_user):
    add_user("bob@example.com", {**BOB_PROFILE, "reminder_time": "07:00:00"}, BOB_TOKEN)
    with session_factory() as db:
        db.execute(
            update(Profile)
            .where(Profile.timezone == "Asia/Kolkata")
            .values(timezone="Nowhere/Land")
        )
        db.commit()
    stats = sweep(session_factory, FakeSender())
    assert (stats.due, stats.sent) == (1, 1)
