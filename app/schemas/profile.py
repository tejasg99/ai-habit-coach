import re
from datetime import datetime, time
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.enums import DietaryPref, FitnessLevel, Goal


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Must be a valid IANA timezone, e.g. 'Asia/kolkata'")
    return value


_EQUIPMENT_RE = re.compile(r"[a-z0-9][a-z0-9 \-]*")


def _clean_equipment(items: list[str]) -> list[str]:
    cleaned = {item.strip().lower() for item in items if item.strip()}
    for item in cleaned:
        if len(item) > 50:
            raise ValueError("Equipment names must be 50 characters or fewer")
        if not _EQUIPMENT_RE.fullmatch(item):
            raise ValueError(
                "Equipment names may only contain letters, numbers, spaces and hyphens"
            )

    return sorted(cleaned)


# Reusable field types: validation rules defined once, used in several schemas.
Timezone = Annotated[str, AfterValidator(_validate_timezone)]
Equipment = Annotated[list[str], Field(max_length=20), AfterValidator(_clean_equipment)]


class ProfileIn(BaseModel):
    """Full profile: used by PUT(create or replace)"""

    goal: Goal
    fitness_level: FitnessLevel
    dietary_pref: DietaryPref
    equipment: Equipment = Field(default_factory=list)
    timezone: Timezone = "UTC"
    reminder_time: time = time(20, 0)  # in the user's local time


class ProfileUpdate(BaseModel):
    """Partial profile: used by PATCH. Every field is optional."""

    goal: Goal | None = None
    fitness_level: FitnessLevel | None = None
    dietary_pref: DietaryPref | None = None
    equipment: Equipment | None = None
    timezone: Timezone | None = None
    reminder_time: time | None = None


class ProfileRead(ProfileIn):
    model_config = ConfigDict(from_attributes=True)

    onboarding_complete: bool
    updated_at: datetime
