from datetime import date

from pydantic import BaseModel, ConfigDict


class StreakRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_streak: int
    longest_streak: int
    last_completed_date: date | None
    completed_today: bool
