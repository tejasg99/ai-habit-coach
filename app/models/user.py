from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.log import Log
    from app.models.plan import Plan
    from app.models.profile import Profile
    from app.models.push_token import PushToken
    from app.models.reminder_send import ReminderSend


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Optional["Profile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    plans: Mapped[list["Plan"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    logs: Mapped[list["Log"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    push_tokens: Mapped[list["PushToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    
    reminder_sends: Mapped[list["ReminderSend"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
