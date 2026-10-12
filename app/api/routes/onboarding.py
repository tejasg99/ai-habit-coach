from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.profile import ProfileIn, ProfileRead, ProfileUpdate
from app.services.profiles import (
    ProfileNotFoundError,
    get_profile,
    save_profile,
    update_profile,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

@router.put("/me", response_model=ProfileRead)
def save_my_profile(payload: ProfileIn, user: CurrentUser, db: DbSession):
    return save_profile(db, user.id, payload.model_dump())


@router.get("/me", response_model=ProfileRead)
def read_my_profile(user: CurrentUser, db: DbSession):
    profile = get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Onboarding not completed")
    return profile

@router.patch("/me", response_model=ProfileRead)
def update_my_profile(payload: ProfileUpdate, user: CurrentUser, db: DbSession):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    try:
        return update_profile(db, user.id, changes)
    except ProfileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Onboarding not completed")

