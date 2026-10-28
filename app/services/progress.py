from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.log import Log
from app.models.plan import Plan, PlanItem
from app.services.plans import user_timezone, user_today
from app.services.streaks import StreakInfo, get_streak


@dataclass(frozen=True)
class PlanSchedule:
    """What one plan scheduled, and the local date from which it applied."""

    effective_from: date
    items_per_weekday: Mapping[int, int]  # 0 = Monday ... 6 = Sunday


@dataclass(frozen=True)
class DayProgress:
    day: date
    planned: int
    completed: int
    completion_rate: float | None  # None when nothing was planned


@dataclass(frozen=True)
class Progress:
    start_date: date
    end_date: date
    days: list[DayProgress]
    total_completed: int
    active_days: int
    streak: StreakInfo


def build_daily_progress(
    start: date,
    end: date,
    schedules: list[PlanSchedule],
    completed_by_day: Mapping[date, int],
) -> list[DayProgress]:
    """One entry per date from start to end inclusive, oldest first. Pure: no DB, no clock.

    `schedules` must be given in generation order. If two plans took effect on the same
    date, the later one wins (the sort is stable and bisect_right picks the last tie).
    """
    ordered = sorted(schedules, key=lambda s: s.effective_from)
    starts = [s.effective_from for s in ordered]

    days = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        index = bisect_right(starts, day) - 1  # the last plan in effect on or before `day`
        planned = ordered[index].items_per_weekday.get(day.weekday(), 0) if index >= 0 else 0
        completed = completed_by_day.get(day, 0)
        # Capped at 1.0: a mid-day regeneration can leave more completions than the new plan lists.
        rate = round(min(completed / planned, 1.0), 3) if planned else None
        days.append(DayProgress(day, planned, completed, rate))
    return days


def _local_date(moment: datetime, tz_name: str) -> date:
    if moment.tzinfo is None:  # SQLite drops tzinfo; every stored moment is UTC
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(tz_name)).date()


def _load_schedules(db: Session, user_id: int, tz_name: str) -> list[PlanSchedule]:
    """One query: items per weekday for every plan the user ever had, oldest plan first."""
    rows = db.execute(
        select(Plan.id, Plan.generated_at, PlanItem.day_of_week, func.count(PlanItem.id))
        .join(PlanItem, PlanItem.plan_id == Plan.id)
        .where(Plan.user_id == user_id)
        .group_by(Plan.id, Plan.generated_at, PlanItem.day_of_week)
        .order_by(Plan.generated_at, Plan.id)
    ).all()

    effective: dict[int, date] = {}
    counts: dict[int, dict[int, int]] = {}
    for plan_id, generated_at, weekday, n in rows:
        effective.setdefault(plan_id, _local_date(generated_at, tz_name))
        counts.setdefault(plan_id, {})[weekday] = n
    return [PlanSchedule(effective[plan_id], counts[plan_id]) for plan_id in effective]


def get_progress(db: Session, user_id: int, days: int) -> Progress:
    tz_name = user_timezone(db, user_id)
    end = user_today(db, user_id)
    start = end - timedelta(days=days - 1)

    completed_rows = db.execute(
        select(Log.log_date, func.count(Log.id))
        .where(Log.user_id == user_id, Log.log_date >= start, Log.log_date <= end)
        .group_by(Log.log_date)
    ).all()
    completed_by_day = {log_date: n for log_date, n in completed_rows}

    daily = build_daily_progress(
        start, end, _load_schedules(db, user_id, tz_name), completed_by_day
    )
    return Progress(
        start_date=start,
        end_date=end,
        days=daily,
        total_completed=sum(d.completed for d in daily),
        active_days=sum(1 for d in daily if d.completed > 0),
        streak=get_streak(db, user_id),
    )
