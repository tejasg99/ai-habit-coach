import logging
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import PlanStatus
from app.models.plan import Plan, PlanItem
from app.schemas.plan_generation import GeneratedPlan
from app.services.llm_client import chat_completion
from app.services.plan_prompt import PROMPT_VERSION, build_plan_messages
from app.services.profiles import get_profile

logger = logging.getLogger(__name__)

MAX_GENERATIONS_PER_DAY = 5
MAX_OUTPUT_ATTEMPTS = 2  # how many times we ask when the model's JSON fails validation


class ProfileIncompleteError(Exception):
    """The user hasn't completed onboarding."""


class GenerationLimitError(Exception):
    """The user used up today's plan generations."""


class GenerationConflictError(Exception):
    """Another generation for this user finished first."""


class PlanGenerationError(Exception):
    """The model answered, but never with a valid plan."""


def clean_json_text(raw: str) -> str:
    """Keep only the part from the first '{' to the last '}'.
    Strips markdown fences and chatty text around the JSON."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        return raw.strip()
    return raw[start : end + 1]


def _summarize(exc: ValidationError, limit: int = 3) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:limit]
    )


def _build_plan(user_id: int, parsed: GeneratedPlan, raw: str, attempt: int) -> Plan:
    items = [
        PlanItem(
            day_of_week=day.day.index,
            position=position,
            type=item.type,
            title=item.title,
            description=item.description,
            target_metric=item.target_metric,
        )
        for day in parsed.days
        for position, item in enumerate(day.items)
    ]
    return Plan(
        user_id=user_id,
        status=PlanStatus.active,
        prompt_version=PROMPT_VERSION,
        llm_model=settings.LLM_MODEL or None,
        raw_llm_response={"raw_text": raw, "attempt": attempt},
        items=items,
    )


def generate_plan(db: Session, user_id: int) -> Plan:
    # 1. Read phase: cheap checks first, so we never pay for an LLM call we'd have to reject.
    profile = get_profile(db, user_id)
    if profile is None or not profile.onboarding_complete:
        raise ProfileIncompleteError

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    used = db.scalar(
        select(func.count())
        .select_from(Plan)
        .where(Plan.user_id == user_id, Plan.generated_at >= since)
    )
    if used >= MAX_GENERATIONS_PER_DAY:
        raise GenerationLimitError

    messages = build_plan_messages(profile)

    # 2. End the read transaction so we don't hold a pooled DB connection during the slow call.
    #    (expire_on_commit=False, so loaded objects stay usable.)
    db.commit()

    # 3. Slow phase: ask the model, validate, and ask again if the OUTPUT was unusable.
    parsed, raw, attempt, last_error = None, "", 0, None
    for attempt in range(1, MAX_OUTPUT_ATTEMPTS + 1):
        raw = chat_completion(messages)  # LLM errors propagate to the route
        try:
            parsed = GeneratedPlan.model_validate_json(clean_json_text(raw))
            break
        except ValidationError as exc:
            last_error = exc
            logger.warning(
                "LLM output failed validation (attempt %s/%s): %s",
                attempt,
                MAX_OUTPUT_ATTEMPTS,
                _summarize(exc),
            )
    if parsed is None:
        raise PlanGenerationError("Model never produced a valid plan") from last_error

    # 4. Write phase: archive the old plan and insert the new one in ONE transaction.
    #    Order matters: the unique index allows only one 'active' plan per user.
    db.execute(
        update(Plan)
        .where(Plan.user_id == user_id, Plan.status == PlanStatus.active)
        .values(status=PlanStatus.archived)
    )
    plan = _build_plan(user_id, parsed, raw, attempt)
    db.add(plan)
    try:
        db.commit()
    except IntegrityError:  # a concurrent request inserted its active plan first
        db.rollback()
        logger.warning("Active-plan conflict for user %s", user_id, exc_info=True)
        raise GenerationConflictError from None
    db.refresh(plan)
    return plan
