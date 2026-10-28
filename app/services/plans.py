from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PlanStatus
from app.models.log import Log
from app.models.plan import Plan, PlanItem
from app.services.profiles import get_profile


@dataclass
class TodayView:
    plan_id: int
    local_date: date
    weekday: int
    items: list[PlanItem]
    log_ids: dict[int, int]  # plan_item_id -> log id, for items completed today


def get_active_plan(db: Session, user_id: int) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.user_id == user_id, Plan.status == PlanStatus.active))


def local_today(tz_name: str, now: datetime | None = None) -> date:
    """The current calendar date for someone in the given timezone."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(tz_name)).date()


def user_timezone(db: Session, user_id: int) -> str:
    profile = get_profile(db, user_id)
    return profile.timezone if profile else "UTC"


def user_today(db: Session, user_id: int) -> date:
    """THE place that decides what 'today' means for a user. Everything else calls this."""
    return local_today(user_timezone(db, user_id))


def items_for_weekday(plan: Plan, weekday: int) -> list[PlanItem]:
    return [item for item in plan.items if item.day_of_week == weekday]


def get_today(db: Session, user_id: int) -> TodayView | None:
    plan = get_active_plan(db, user_id)
    if plan is None:
        return None

    today = user_today(db, user_id)
    items = items_for_weekday(plan, today.weekday())

    log_ids: dict[int, int] = {}
    if items:
        rows = db.execute(
            select(Log.plan_item_id, Log.id).where(
                Log.user_id == user_id,
                Log.log_date == today,
                Log.plan_item_id.in_([item.id for item in items]),
            )
        ).all()
        log_ids = {plan_item_id: log_id for plan_item_id, log_id in rows}

    return TodayView(
        plan_id=plan.id,
        local_date=today,
        weekday=today.weekday(),
        items=items,
        log_ids=log_ids,
    )
