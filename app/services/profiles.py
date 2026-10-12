from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Profile

class ProfileNotFoundError(Exception):
    pass

def get_profile(db: Session, user_id: int) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))

def save_profile(db: Session, user_id: int, data: dict) -> Profile:
    """Create the profile if it doesn't exist, otherwise replace its fields."""
    profile = get_profile(db, user_id)
    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)

    for field, value in data.items():
        setattr(profile, field, value)
    profile.onboarding_complete = True

    db.commit()
    db.refresh(profile)
    return profile

def update_profile(db: Session, user_id: int, changes: dict) -> Profile:
    """Apply only the given fields. The profile must already exist."""
    profile = get_profile(db, user_id)
    if profile is None:
        raise ProfileNotFoundError

    for field, value in changes.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile