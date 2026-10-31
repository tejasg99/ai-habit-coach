from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.push_token import PushToken


def _find(db: Session, token: str) -> PushToken | None:
    return db.scalar(select(PushToken).where(PushToken.token == token))


def register_token(db: Session, user_id: int, token: str) -> None:
    """Idempotent. If the token already exists it is re-pointed at this user: the same
    phone may have been used by someone else before (logout, then another login)."""
    existing = _find(db, token)
    if existing is None:
        db.add(PushToken(user_id=user_id, token=token))
        try:
            db.commit()
            return
        except IntegrityError:  # a concurrent request inserted the same token first
            db.rollback()
            existing = _find(db, token)
            if existing is None:
                raise
    existing.user_id = user_id
    db.commit()


def unregister_token(db: Session, user_id: int, token: str) -> None:
    """Scoped by user: you can only remove your own tokens. Removing a missing one is fine."""
    db.execute(delete(PushToken).where(PushToken.token == token, PushToken.user_id == user_id))
    db.commit()
