from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.session import DbSession
from app.schemas.errors import ErrorDetail
from app.schemas.token import RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services.login_throttle import (
    RETRY_AFTER_SECONDS,
    LoginThrottledError,
    clear_login_failures,
    ensure_login_allowed,
    record_login_failure,
)
from app.services.users import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    create_user,
    get_user_by_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: DbSession):
    try:
        return create_user(db, payload.email, payload.password, payload.display_name)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")


@router.post(
    "/login",
    response_model=TokenPair,
    responses={
        401: {"model": ErrorDetail, "description": "Incorrect email or password"},
        429: {"model": ErrorDetail, "description": "Too many failed attempts (see Retry-After)"},
    },
)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    try:
        ensure_login_allowed(db, form.username)  # before any password hashing
    except LoginThrottledError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )

    user = authenticate_user(db, form.username, form.password)
    if user is None:
        record_login_failure(db, form.username)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    clear_login_failures(db, form.username)
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(body: RefreshRequest, db: DbSession):
    try:
        user_id = decode_token(body.refresh_token, expected_type=REFRESH)
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if get_user_by_id(db, user_id) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _issue_tokens(user_id)
