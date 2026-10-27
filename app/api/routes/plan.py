from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DbSession
from app.schemas.plan import PlanRead, TodayItemRead, TodayRead
from app.services.llm_client import LLMError, LLMUnavailableError
from app.services.plan_generator import (
    MAX_GENERATIONS_PER_DAY,
    GenerationConflictError,
    GenerationLimitError,
    PlanGenerationError,
    ProfileIncompleteError,
    generate_plan,
)
from app.services.plans import TodayView, get_active_plan, get_today

router = APIRouter(prefix="/plan", tags=["plan"])


@router.post("/generate", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def generate(user: CurrentUser, db: DbSession):
    try:
        return generate_plan(db, user.id)
    except ProfileIncompleteError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Complete onboarding before generating a plan"
        )
    except GenerationLimitError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily limit of {MAX_GENERATIONS_PER_DAY} plan generations reached",
        )
    except GenerationConflictError:
        raise HTTPException(status.HTTP_409_CONFLICT, "A plan generation just finished; try again")
    except LLMUnavailableError:  # must come BEFORE LLMError: it's a subclass
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The plan generator is busy. Please try again shortly.",
            headers={"Retry-After": "30"},
        )
    except (PlanGenerationError, LLMError):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Could not produce a valid plan. Please try again."
        )


def _today_response(view: TodayView) -> TodayRead:
    items = []
    for item in view.items:
        log_id = view.log_ids.get(item.id)
        items.append(
            TodayItemRead.model_validate(item).model_copy(
                update={"completed": log_id is not None, "log_id": log_id}
            )
        )
    return TodayRead(
        plan_id=view.plan_id,
        local_date=view.local_date,
        weekday=view.weekday,
        items=items,
    )


@router.get("/today", response_model=TodayRead)
def today(user: CurrentUser, db: DbSession):
    view = get_today(db, user.id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active plan. Generate one first.")
    return _today_response(view)


@router.get("/week", response_model=PlanRead)
def week(user: CurrentUser, db: DbSession):
    plan = get_active_plan(db, user.id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active plan. Generate one first.")
    return plan
