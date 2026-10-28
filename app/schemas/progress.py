from datetime import date

from pydantic import BaseModel, ConfigDict


class StreakRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_streak: int
    longest_streak: int
    last_completed_date: date | None
    completed_today: bool


class DayProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    planned: int
    completed: int
    completion_rate: float | None


class ProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_date: date
    end_date: date
    days: list[DayProgressRead]
    total_completed: int
    active_days: int
    streak: StreakRead
