from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.login_failure import LoginFailure

WINDOW = timedelta(minutes=15)
MAX_FAILURES = 5
RETRY_AFTER_SECONDS = int(WINDOW.total_seconds())  # a conservative upper bound


class LoginThrottledError(Exception):
    """Too many recent failed logins for this email."""


def _key(email: str) -> str:
    return email.strip().lower()[:255]  # also bounds what an attacker can make us store


def ensure_login_allowed(db: Session, email: str, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    recent = db.scalar(
        select(func.count())
        .select_from(LoginFailure)
        .where(LoginFailure.email == _key(email), LoginFailure.created_at >= now - WINDOW)
    )
    if recent >= MAX_FAILURES:
        raise LoginThrottledError


def record_login_failure(db: Session, email: str, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    db.add(LoginFailure(email=_key(email), created_at=now))
    # Housekeeping: rows older than the window can never matter again, so the table
    # cannot grow without bound however many fake emails someone tries.
    db.execute(delete(LoginFailure).where(LoginFailure.created_at < now - WINDOW))
    db.commit()


def clear_login_failures(db: Session, email: str) -> None:
    db.execute(delete(LoginFailure).where(LoginFailure.email == _key(email)))
    db.commit()
