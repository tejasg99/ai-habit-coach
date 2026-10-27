from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.log import Log
from app.services.plans import user_today


@dataclass(frozen=True)
class StreakInfo:
    current_streak: int
    longest_streak: int
    last_completed_date: date | None
    completed_today: bool


def compute_streak(dates: Iterable[date], today: date) -> StreakInfo:
    """A day counts if at least one item was logged on it. Pure: dates in, numbers out.

    The current streak stays alive until the user has missed an entire day: if the last
    log was today OR yesterday, it still counts, because today isn't over yet.
    """
    days = sorted(set(dates))  # duplicates and ordering don't matter
    if not days:
        return StreakInfo(0, 0, None, False)

    run = longest = 1
    for previous, current in pairwise(days):
        run = run + 1 if (current - previous).days == 1 else 1
        longest = max(longest, run)

    last = days[-1]
    # <= 1 also covers a negative gap: a user who moved to an earlier timezone can have
    # a log "from the future". We keep their streak rather than punishing them.
    alive = (today - last).days <= 1
    return StreakInfo(
        current_streak=run if alive else 0,  # `run` is the run that ends at the last log
        longest_streak=longest,
        last_completed_date=last,
        completed_today=(last == today),
    )


def get_streak(db: Session, user_id: int) -> StreakInfo:
    today = user_today(db, user_id)
    dates = db.scalars(select(Log.log_date).where(Log.user_id == user_id).distinct()).all()
    return compute_streak(dates, today)
