from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PlanItemType, PlanStatus


class PlanItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_of_week: int
    position: int
    type: PlanItemType
    title: str
    description: str
    target_metric: str | None


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PlanStatus
    generated_at: datetime
    items: list[PlanItemRead]
    # raw_llm_response, prompt_version and llm_model are internal: not listed, so never exposed.


class TodayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: int
    local_date: date  # the user's local date, not UTC
    weekday: int  # 0 = Monday
    items: list[PlanItemRead]
