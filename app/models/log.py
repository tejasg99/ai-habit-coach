from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.plan import PlanItem
from app.models.user import User


class Log(Base):
    """One row means: this user completed this plan item on this (user-local) date."""

    __tablename__ = "logs"
    __table_args__ = (
        # Makes "mark complete" idempotent: retries and double taps cannot create duplicates.
        UniqueConstraint("user_id", "plan_item_id", "log_date", name="uq_logs_user_item_date"),
        # Serves "all of this user's dates": the streak and progress queries.
        Index("ix_logs_user_date", "user_id", "log_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_item_id: Mapped[int] = mapped_column(
        ForeignKey("plan_items.id", ondelete="CASCADE"), index=True
    )
    log_date: Mapped[date] = mapped_column(Date)  # the user's local date, not UTC
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    value: Mapped[Optional[float]] = mapped_column(nullable=True)  # actual reps/weight, if logged

    user: Mapped[User] = relationship(back_populates="logs")
    plan_item: Mapped[PlanItem] = relationship()