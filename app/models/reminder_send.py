from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class ReminderSend(Base):
    """Ledger: a row means 'this user's reminder for this local day was claimed'."""

    __tablename__ = "reminder_sends"
    __table_args__ = (
        # The whole idempotency guarantee lives here, enforced by the database.
        UniqueConstraint("user_id", "local_date", name="uq_reminder_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    local_date: Mapped[date] = mapped_column(Date)  # the user's local day, not UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="reminder_sends")