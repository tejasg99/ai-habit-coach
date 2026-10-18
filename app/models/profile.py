from datetime import datetime, time

from sqlalchemy import JSON, DateTime, ForeignKey, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DietaryPref, FitnessLevel, Goal, enum_column
from app.models.user import User


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    goal: Mapped[Goal] = mapped_column(enum_column(Goal))
    fitness_level: Mapped[FitnessLevel] = mapped_column(enum_column(FitnessLevel))
    dietary_pref: Mapped[DietaryPref] = mapped_column(enum_column(DietaryPref))
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)

    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    reminder_time: Mapped[time] = mapped_column(Time, default=time(20, 0))

    onboarding_complete: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")
