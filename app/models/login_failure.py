from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginFailure(Base):
    """One row per failed login, used for throttling. No foreign key on purpose:
    attempts for emails that don't exist must be recorded too."""

    __tablename__ = "login_failures"
    __table_args__ = (Index("ix_login_failures_email_created", "email", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
