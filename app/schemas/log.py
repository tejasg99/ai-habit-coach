from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LogCreate(BaseModel):
    # Unknown fields are a 422: a client that sends "log_date" learns the server decides it.
    model_config = ConfigDict(extra="forbid")

    plan_item_id: int = Field(gt=0)
    value: float | None = Field(default=None, ge=0, le=100_000, allow_inf_nan=False)


class LogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_item_id: int
    log_date: date
    completed_at: datetime
    value: float | None
