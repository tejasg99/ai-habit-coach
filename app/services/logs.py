from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import PlanStatus
from app.models.log import Log
from app.models.plan import Plan, PlanItem
from app.services.plans import user_today


class PlanItemNotFoundError(Exception):
    """No such item, or it isn't in the caller's active plan. We deliberately don't say which."""


class ItemNotScheduledTodayError(Exception):
    """The item exists but belongs to a different weekday."""


class LogNotFoundError(Exception):
    pass


class LogNotEditableError(Exception):
    """Only today's completions can be undone."""


def _find_log(db: Session, user_id: int, plan_item_id: int, log_date: date) -> Log | None:
    return db.scalar(
        select(Log).where(
            Log.user_id == user_id,
            Log.plan_item_id == plan_item_id,
            Log.log_date == log_date,
        )
    )


def _get_loggable_item(db: Session, user_id: int, plan_item_id: int) -> PlanItem | None:
    """An item the caller owns AND that belongs to their current (active) plan.
    Ownership is part of the query itself, so another user's id simply finds nothing."""
    return db.scalar(
        select(PlanItem)
        .join(Plan, PlanItem.plan_id == Plan.id)
        .where(
            PlanItem.id == plan_item_id,
            Plan.user_id == user_id,
            Plan.status == PlanStatus.active,
        )
    )


def log_completion(
    db: Session, user_id: int, plan_item_id: int, value: float | None
) -> tuple[Log, bool]:
    """Mark an item done today. Returns (log, created). Safe to call repeatedly."""
    today = user_today(db, user_id)

    item = _get_loggable_item(db, user_id, plan_item_id)
    if item is None:
        raise PlanItemNotFoundError
    if item.day_of_week != today.weekday():
        raise ItemNotScheduledTodayError

    existing = _find_log(db, user_id, plan_item_id, today)
    if existing is not None:
        return existing, False

    log = Log(user_id=user_id, plan_item_id=plan_item_id, log_date=today, value=value)
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced past the check above; the unique constraint caught it.
        db.rollback()
        existing = _find_log(db, user_id, plan_item_id, today)
        if existing is None:
            raise  # some other integrity problem: don't hide it
        return existing, False
    db.refresh(log)
    return log, True


def delete_log(db: Session, user_id: int, log_id: int) -> None:
    log = db.scalar(select(Log).where(Log.id == log_id, Log.user_id == user_id))
    if log is None:
        raise LogNotFoundError  # ownership check first
    if log.log_date != user_today(db, user_id):
        raise LogNotEditableError
    db.delete(log)
    db.commit()
