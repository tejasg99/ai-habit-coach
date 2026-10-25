from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PlanStatus
from app.models.plan import Plan, PlanItem
from app.services.profiles import get_profile


@dataclass
class TodayView:
    plan_id: int
    local_date: date
    weekday: int
    items: list[PlanItem]


def get_active_plan(db: Session, user_id: int) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.user_id == user_id, Plan.status == PlanStatus.active))


def local_today(tz_name: str, now: datetime | None = None) -> date:
    """The current calendar date for someone in the given timezone."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(tz_name)).date()


def items_for_weekday(plan: Plan, weekday: int) -> list[PlanItem]:
    return [item for item in plan.items if item.day_of_week == weekday]


def get_today(db: Session, user_id: int) -> TodayView | None:
    plan = get_active_plan(db, user_id)
    if plan is None:
        return None
    profile = get_profile(db, user_id)
    today = local_today(profile.timezone if profile else "UTC")
    return TodayView(
        plan_id=plan.id,
        local_date=today,
        weekday=today.weekday(),
        items=items_for_weekday(plan, today.weekday()),
    )
