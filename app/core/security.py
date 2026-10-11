from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_password_hash = PasswordHash.recommended()

ACCESS = "access"
REFRESH = "refresh"

class TokenError(Exception):
    """Any invalid, expired or wront-type token."""

def hash_password(password: str) -> str:
    return _password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)

# Verified against when an email doesn't exist, so login takes roughly the same
# time either way (otherwise response time reveals which emails are registered).
DUMMY_HASH = hash_password("not-a-real-password")

def _create_token(user_id: int, token_type: str, expires_in: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(user_id: int) -> str:
    return _create_token(user_id, ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

def decode_token(token: str, expected_type: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload["type"] != expected_type:
        raise TokenError("Wrong token type")
    try:
        return int(payload["sub"])
    except ValueError as exc:
        raise TokenError("Malformed subject") from exc