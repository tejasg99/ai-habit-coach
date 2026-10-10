from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User

class EmailAlreadyRegisteredError(Exception):
    pass

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))

def create_user(
        db: Session, email: str, password: str, display_name: str | None = None
) -> User:
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