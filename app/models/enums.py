import enum

from sqlalchemy import Enum


class Goal(str, enum.Enum):
    lose_weight = "lose_weight"
    build_muscle = "build_muscle"
    stay_active = "stay_active"
    improve_endurance = "improve_endurance"


class FitnessLevel(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class DietaryPref(str, enum.Enum):
    non_vegetarian = "non_vegetarian"
    eggetarian = "eggetarian"
    vegetarian = "vegetarian"
    vegan = "vegan"


class PlanStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class PlanItemType(str, enum.Enum):
    workout = "workout"
    meal = "meal"
    habit = "habit"


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    return Enum(
        enum_cls, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e]
    )
