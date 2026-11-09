from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.errors import ErrorDetail
from app.schemas.log import LogCreate, LogRead
from app.services.logs import (
    ItemNotScheduledTodayError,
    LogNotEditableError,
    LogNotFoundError,
    PlanItemNotFoundError,
    delete_log,
    log_completion,
)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post(
    "",
    response_model=LogRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": LogRead,
            "description": "Already logged today; the existing log is returned",
        },
        404: {"model": ErrorDetail, "description": "Plan item not found"},
        409: {"model": ErrorDetail, "description": "This item is not scheduled for today"},
    },
)
def create_log(payload: LogCreate, response: Response, user: CurrentUser, db: DbSession):
    try:
        log, created = log_completion(db, user.id, payload.plan_item_id, payload.value)
    except PlanItemNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan item not found")
    except ItemNotScheduledTodayError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This item is not scheduled for today")
    if not created:
        response.status_code = status.HTTP_200_OK  # already logged: same result, nothing new made
    return log


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorDetail, "description": "Log not found"},
        409: {"model": ErrorDetail, "description": "Only today's completions can be undone"},
    },
)
def remove_log(log_id: int, user: CurrentUser, db: DbSession):
    try:
        delete_log(db, user.id, log_id)
    except LogNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Log not found")
    except LogNotEditableError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only today's completions can be undone")
