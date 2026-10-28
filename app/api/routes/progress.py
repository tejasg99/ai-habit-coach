from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.progress import ProgressRead, StreakRead
from app.services.progress import get_progress
from app.services.streaks import get_streak

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressRead)
def read_progress(user: CurrentUser, db: DbSession, days: Annotated[int, Query(ge=1, le=90)] = 30):
    return get_progress(db, user.id, days)


@router.get("/streak", response_model=StreakRead)
def read_streak(user: CurrentUser, db: DbSession):
    return get_streak(db, user.id)
