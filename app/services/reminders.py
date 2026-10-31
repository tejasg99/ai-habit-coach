import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import PlanStatus
from app.models.log import Log
from app.models.plan import Plan, PlanItem
from app.models.profile import Profile
from app.models.push_token import PushToken
from app.models.reminder_send import ReminderSend
from app.services.expo_push import (
    PushError,
    PushMessage,
    PushResult,
    PushUnavailableError,
    send_push,
)
from app.services.streaks import StreakInfo, compute_streak

logger = logging.getLogger(__name__)

REMINDER_GRACE = timedelta(hours=2)
MAX_TOKENS_PER_USER = 10  # newest first; older tokens are probably stale

Sender = Callable[[list[PushMessage]], list[PushResult]]


def reminder_local_date(
    now: datetime, tz_name: str, reminder_time: time, grace: timedelta = REMINDER_GRACE
) -> date | None:
    """If a reminder is due right now for someone in this timezone, return their local date.

    Pure: no database, no clock. Compares wall-clock times, which makes it behave sensibly
    around daylight-saving changes. The window never extends past local midnight.
    """
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    local = now.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
    start = datetime.combine(local.date(), reminder_time)
    midnight = datetime.combine(local.date() + timedelta(days=1), time.min)
    end = min(start + grace, midnight)
    return local.date() if start <= local < end else None


def build_reminder(streak: StreakInfo) -> tuple[str, str]:
    """The message text. Contains no personal data: it appears on lock screens."""
    if streak.current_streak >= 2:
        return (
            f"Keep your {streak.current_streak}-day streak alive",
            "Log one activity from today's plan to keep it going.",
        )
    return (
        "Ready for today's plan?",
        "Your plan for today is waiting. One activity is enough to get started.",
    )


@dataclass
class SweepStats:
    considered: int = 0  # users who could get a reminder (finished onboarding, have a device)
    due: int = 0  # ...and are inside their reminder window right now
    skipped: int = 0  # nothing to remind about, or already handled
    sent: int = 0  # at least one device accepted the message
    released: int = 0  # Expo was unavailable; the claim was released, so the next sweep retries
    failed: int = 0  # nothing was delivered and we will not retry today
    pruned_tokens: int = 0


def _plan_untouched_today(db: Session, user_id: int, local_date: date) -> bool:
    """True if today's plan has items and the user has logged nothing yet today."""
    planned = db.scalar(
        select(func.count(PlanItem.id))
        .select_from(PlanItem)
        .join(Plan, PlanItem.plan_id == Plan.id)
        .where(
            Plan.user_id == user_id,
            Plan.status == PlanStatus.active,
            PlanItem.day_of_week == local_date.weekday(),
        )
    )
    if not planned:
        return False
    done = db.scalar(
        select(func.count(Log.id)).where(Log.user_id == user_id, Log.log_date == local_date)
    )
    return done == 0


def _claim(db: Session, user_id: int, local_date: date) -> ReminderSend | None:
    """Try to claim today's reminder. Exactly one caller can ever win."""
    claim = ReminderSend(user_id=user_id, local_date=local_date)
    db.add(claim)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return claim


def _release(db: Session, claim: ReminderSend) -> None:
    db.delete(claim)
    db.commit()


def _process_user(
    db: Session, user_id: int, local_date: date, sender: Sender, stats: SweepStats
) -> None:
    if not _plan_untouched_today(db, user_id, local_date):
        stats.skipped += 1
        return

    claim = _claim(db, user_id, local_date)
    if claim is None:  # another sweep got here first
        stats.skipped += 1
        return

    tokens = db.scalars(
        select(PushToken.token)
        .where(PushToken.user_id == user_id)
        .order_by(PushToken.id.desc())
        .limit(MAX_TOKENS_PER_USER)
    ).all()
    if not tokens:  # removed since we looked: give the day back
        _release(db, claim)
        stats.skipped += 1
        return

    dates = db.scalars(select(Log.log_date).where(Log.user_id == user_id).distinct()).all()
    title, body = build_reminder(compute_streak(dates, local_date))
    messages = [PushMessage(to=t, title=title, body=body, data={"screen": "today"}) for t in tokens]

    try:
        results = sender(messages)
    except PushUnavailableError:
        _release(db, claim)  # a temporary problem: let the next sweep try again
        stats.released += 1
        return
    except PushError:
        # Probably bad credentials. Keep the claim, otherwise every sweep would hammer Expo.
        logger.exception("Expo rejected the reminder for user %s", user_id)
        stats.failed += 1
        return

    dead = [r.token for r in results if r.status == "invalid_token"]
    if dead:
        db.execute(delete(PushToken).where(PushToken.token.in_(dead)))
        db.commit()
        stats.pruned_tokens += len(dead)

    if any(r.status == "ok" for r in results):
        stats.sent += 1
    else:
        stats.failed += 1


def run_reminder_sweep(db: Session, now: datetime, sender: Sender = send_push) -> SweepStats:
    """Send a reminder to every user who is due one. Safe to run any number of times,
    even at the same moment: each user gets at most one reminder per local day."""
    stats = SweepStats()
    profiles = db.scalars(
        select(Profile).where(
            Profile.onboarding_complete.is_(True),
            exists().where(PushToken.user_id == Profile.user_id),
        )
    ).all()
    stats.considered = len(profiles)

    # Plain tuples, not ORM objects: a rollback later in the loop expires every loaded object.
    due: list[tuple[int, date]] = []
    for profile in profiles:
        try:
            local_date = reminder_local_date(now, profile.timezone, profile.reminder_time)
        except Exception:  # one corrupt row must not stop everyone else's reminders
            logger.exception("Bad reminder settings for user %s", profile.user_id)
            continue
        if local_date is not None:
            due.append((profile.user_id, local_date))
    stats.due = len(due)
    if not due:
        return stats

    # One query tells us who is already handled, so repeat sweeps stay cheap.
    handled = {
        (user_id, local_date)
        for user_id, local_date in db.execute(
            select(ReminderSend.user_id, ReminderSend.local_date).where(
                ReminderSend.local_date.in_({d for _, d in due})
            )
        )
    }

    for user_id, local_date in due:
        if (user_id, local_date) in handled:
            stats.skipped += 1
            continue
        try:
            _process_user(db, user_id, local_date, sender, stats)
        except Exception:  # isolate failures: the claim (if made) stays, so no duplicates
            db.rollback()
            logger.exception("Reminder failed for user %s", user_id)
            stats.failed += 1
    return stats
