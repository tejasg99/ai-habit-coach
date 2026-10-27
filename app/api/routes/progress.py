from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.progress import StreakRead
from app.services.streaks import get_streak

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/streak", response_model=StreakRead)
def read_streak(user: CurrentUser, db: DbSession):
    return get_streak(db, user.id)
