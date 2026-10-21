from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PlanItemType, PlanStatus, enum_column
from app.models.user import User


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        # At most ONE active plan per user, enforced by the database itself.
        Index(
            "uq_plans_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[PlanStatus] = mapped_column(enum_column(PlanStatus), default=PlanStatus.active)

    # Debugging trail: what we asked, which model answered, and exactly what it said.
    prompt_version: Mapped[str] = mapped_column(String(20), default="v1")
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_llm_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="plans")
    items: Mapped[list["PlanItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanItem.day_of_week, PlanItem.position",
    )


class PlanItem(Base):
    __tablename__ = "plan_items"
    __table_args__ = (CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_plan_items_dow"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int]  # 0 = Monday ... 6 = Sunday, same as Python's date.weekday()
    position: Mapped[int] = mapped_column(default=0)  # order within the day
    type: Mapped[PlanItemType] = mapped_column(enum_column(PlanItemType))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    target_metric: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="items")
