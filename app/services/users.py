from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models.user import User


class EmailAlreadyRegisteredError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, email: str, password: str, display_name: str | None = None) -> User:
    if get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError

    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        display_name=display_name,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyRegisteredError
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)

    # Always do one hash verification, even for unknown emails
    password_ok = verify_password(password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not password_ok:
        return None
    return user


def update_user(db: Session, user: User, changes: dict) -> User:
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()
