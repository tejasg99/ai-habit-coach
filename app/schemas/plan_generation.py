import enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.models.enums import PlanItemType
from app.schemas.fields import blank_to_none


class Weekday(str, enum.Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"

    @property
    def index(self) -> int:
        """0 = Monday ... 6 = Sunday. The LLM never sees or produces this number."""
        return list(Weekday).index(self)


def _normalize(value):
    return value.strip().lower() if isinstance(value, str) else value


# LLMs capitalize inconsistently ("Workout", " monday "), so we normalize BEFORE validating.
Day = Annotated[Weekday, BeforeValidator(_normalize)]
ItemType = Annotated[PlanItemType, BeforeValidator(_normalize)]

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Metric = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None,
    BeforeValidator(blank_to_none),
]


class GeneratedItem(BaseModel):
    type: ItemType
    title: Title
    description: Description
    target_metric: Metric = None


class GeneratedDay(BaseModel):
    day: Day
    items: list[GeneratedItem] = Field(min_length=1, max_length=8)


class GeneratedPlan(BaseModel):
    days: list[GeneratedDay] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def each_weekday_exactly_once(self) -> "GeneratedPlan":
        if sorted(d.day.index for d in self.days) != list(range(7)):
            raise ValueError("Each weekday, monday to sunday, must appear exactly once")
        self.days.sort(key=lambda d: d.day.index)
        return self
