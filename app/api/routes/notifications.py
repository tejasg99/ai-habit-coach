from fastapi import APIRouter, status

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.notification import PushTokenIn
from app.services.push_tokens import register_token, unregister_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/register-token", status_code=status.HTTP_204_NO_CONTENT)
def register(payload: PushTokenIn, user: CurrentUser, db: DbSession):
    register_token(db, user.id, payload.token)


@router.post("/unregister-token", status_code=status.HTTP_204_NO_CONTENT)
def unregister(payload: PushTokenIn, user: CurrentUser, db: DbSession):
    unregister_token(db, user.id, payload.token)
