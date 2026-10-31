import logging
import random
import time
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BATCH = 100  # Expo accepts at most 100 messages per request
MAX_ATTEMPTS = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PushError(Exception):
    """Expo rejected the request in a way retrying won't fix (bad credentials, bad payload)."""


class PushUnavailableError(PushError):
    """Expo stayed unreachable or overloaded through every retry."""


@dataclass(frozen=True)
class PushMessage:
    to: str
    title: str
    body: str
    data: dict | None = None


@dataclass(frozen=True)
class PushResult:
    token: str
    status: str  # "ok" | "invalid_token" | "failed"
    detail: str = ""


def send_push(
    messages: list[PushMessage],
    *,
    http_client: httpx.Client | None = None,
    sleep=time.sleep,
) -> list[PushResult]:
    """Send up to 100 messages. Returns one result per message, in the same order."""
    if not messages:
        return []
    if len(messages) > MAX_BATCH:
        raise ValueError(f"Expo accepts at most {MAX_BATCH} messages per request")

    headers = {"Accept": "application/json"}
    if settings.EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.EXPO_ACCESS_TOKEN}"
    payload = [_to_payload(m) for m in messages]

    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))
    try:
        body = _post_with_retries(client, headers, payload, sleep)
    finally:
        if owns_client:
            client.close()

    tickets = body.get("data") if isinstance(body, dict) else None
    if not isinstance(tickets, list) or len(tickets) != len(messages):
        raise PushError("Unexpected response shape from Expo")
    return [_to_result(m.to, t) for m, t in zip(messages, tickets, strict=True)]


def _to_payload(message: PushMessage) -> dict:
    payload = {"to": message.to, "title": message.title, "body": message.body, "sound": "default"}
    if message.data:
        payload["data"] = message.data
    return payload


def _to_result(token: str, ticket) -> PushResult:
    if not isinstance(ticket, dict):
        return PushResult(token, "failed", "malformed ticket")
    if ticket.get("status") == "ok":
        return PushResult(token, "ok")
    error = (ticket.get("details") or {}).get("error", "")
    if error == "DeviceNotRegistered":  # the app was uninstalled or notifications were turned off
        return PushResult(token, "invalid_token", error)
    return PushResult(token, "failed", error or str(ticket.get("message", ""))[:200])


def _post_with_retries(client, headers, payload, sleep) -> dict:
    problem = "unknown"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.post(settings.EXPO_PUSH_URL, headers=headers, json=payload)
        except httpx.TransportError as exc:
            problem = f"network error ({type(exc).__name__})"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise PushError("Expo returned invalid JSON") from exc
            if resp.status_code not in RETRYABLE_STATUS:
                # Never log headers: they may contain the access token.
                logger.error("Expo rejected request: HTTP %s %s", resp.status_code, resp.text[:300])
                raise PushError(f"Expo rejected the request (HTTP {resp.status_code})")
            problem = f"HTTP {resp.status_code}"

        if attempt < MAX_ATTEMPTS:
            delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.5)
            logger.warning(
                "Expo attempt %s failed (%s); retrying in %.1fs", attempt, problem, delay
            )
            sleep(delay)

    raise PushUnavailableError(f"Expo unavailable after {MAX_ATTEMPTS} attempts ({problem})")
