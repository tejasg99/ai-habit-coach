from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.login_failure import LoginFailure
from app.services.login_throttle import MAX_FAILURES, RETRY_AFTER_SECONDS

EMAIL, PASSWORD = "tejas@example.com", "correct-horse-battery"


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def fail(client, times, email=EMAIL):
    for _ in range(times):
        assert login(client, email, "wrong-password-1").status_code == 401


def failures(session_factory, email=None):
    with session_factory() as db:
        query = select(func.count()).select_from(LoginFailure)
        if email is not None:
            query = query.where(LoginFailure.email == email)
        return db.scalar(query)


def add_old_failures(session_factory, count, minutes_ago=20):
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    with session_factory() as db:
        db.add_all([LoginFailure(email=EMAIL, created_at=when) for _ in range(count)])
        db.commit()


@pytest.fixture()
def account(register):
    register(EMAIL, PASSWORD)


def test_the_limit_blocks_even_the_correct_password(client, account):
    fail(client, MAX_FAILURES)
    res = login(client)  # right password, but too many recent failures
    assert res.status_code == 429
    assert res.headers["retry-after"] == str(RETRY_AFTER_SECONDS)


def test_a_few_failures_do_not_block(client, account):
    fail(client, MAX_FAILURES - 1)
    assert login(client).status_code == 200


def test_success_resets_the_counter(client, session_factory, account):
    fail(client, MAX_FAILURES - 1)
    assert login(client).status_code == 200
    assert failures(session_factory) == 0
    fail(client, MAX_FAILURES - 1)
    assert login(client).status_code == 200


def test_unknown_emails_are_throttled_the_same_way(client):
    fail(client, MAX_FAILURES, "ghost@example.com")
    assert login(client, "ghost@example.com", "anything-1234").status_code == 429


def test_throttling_is_per_email(client, account, register):
    register("bob@example.com", "bobs-password-123")
    fail(client, MAX_FAILURES)
    assert login(client, "bob@example.com", "bobs-password-123").status_code == 200


def test_email_case_does_not_matter(client, account):
    fail(client, 3, "TEJAS@example.com")
    fail(client, MAX_FAILURES - 3, EMAIL)
    assert login(client).status_code == 429


def test_blocked_attempts_do_not_extend_the_lock(client, session_factory, account):
    fail(client, MAX_FAILURES)
    for _ in range(3):
        assert login(client).status_code == 429
    assert failures(session_factory, EMAIL) == MAX_FAILURES


def test_blocked_requests_never_reach_password_hashing(client, account, monkeypatch):
    fail(client, MAX_FAILURES)

    def explode(*args, **kwargs):
        raise AssertionError("the password was checked while throttled")

    monkeypatch.setattr("app.api.routes.auth.authenticate_user", explode)  # patch where it's USED
    assert login(client).status_code == 429


def test_old_failures_stop_counting(client, session_factory, account):
    add_old_failures(session_factory, MAX_FAILURES)
    assert login(client).status_code == 200


def test_old_rows_are_purged_when_a_new_failure_is_recorded(client, session_factory, account):
    add_old_failures(session_factory, 3)
    fail(client, 1)
    assert failures(session_factory) == 1  # the old rows are gone, the fresh one stays
