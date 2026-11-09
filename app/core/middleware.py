import logging
import re
import time
import uuid

from fastapi import Request

from app.core.request_context import request_id_var

access_logger = logging.getLogger("app.access")
_SAFE_ID = re.compile(r"[A-Za-z0-9_\-]{8,64}")
_QUIET_PATHS = {"/health", "/health/db"}  # hosting platforms poll these constantly


def _ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


async def request_context_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id", "")
    # Never copy arbitrary client text into logs ("log forging"): accept only a safe shape.
    request_id = incoming if _SAFE_ID.fullmatch(incoming) else uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    level = logging.DEBUG if request.url.path in _QUIET_PATHS else logging.INFO
    try:
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "%s %s -> unhandled error (%.0f ms)", request.method, request.url.path, _ms(started)
            )
            raise
        response.headers["X-Request-ID"] = request_id
        access_logger.log(
            level,
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            _ms(started),
        )
        return response
    finally:
        request_id_var.reset(token)
