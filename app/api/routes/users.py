from fastapi import APIRouter, status

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.user import UserRead
from app.services.users import delete_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    return user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: DbSession):
    delete_user(db, user)