from fastapi import APIRouter, HTTPException, status

from app.db.session import DbSession
from app.schemas.user import UserCreate, UserRead
from app.services.users import EmailAlreadyRegisteredError, create_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: DbSession):
    try:
        return create_user(db, payload.email, payload.password, payload.display_name)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")