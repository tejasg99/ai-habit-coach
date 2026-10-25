import logging
import random
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Temporary conditions worth retrying: rate limited (429) or provider-side trouble (5xx).
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    """The call failed in a way retrying won't fix (bad key, bad model, odd response shape)."""


class LLMUnavailableError(LLMError):
    """The provider stayed unavailable (timeouts, 429, 5xx) through every retry."""


def chat_completion(
    messages: list[dict[str, str]],
    *,
    json_mode: bool = True,
    http_client: httpx.Client | None = None,
    sleep=time.sleep,
) -> str:
    """Send chat messages to the configured LLM and return the reply text.

    `http_client` and `sleep` exist so tests can inject a fake transport and skip real waiting.
    """
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload: dict = {"model": settings.LLM_MODEL, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    owns_client = http_client is None
    client = http_client or httpx.Client(
        timeout=httpx.Timeout(settings.LLM_TIMEOUT_SECONDS, connect=10.0)
    )
    try:
        return _post_with_retries(client, url, headers, payload, sleep)
    finally:
        if owns_client:
            client.close()


def _post_with_retries(client, url, headers, payload, sleep) -> str:
    problem = "unknown"
    for attempt in range(1, settings.LLM_MAX_ATTEMPTS + 1):
        try:
            resp = client.post(url, headers=headers, json=payload)
        except httpx.TransportError as exc:  # timeouts, DNS failures, dropped connections
            problem = f"Network error ({type(exc).__name__})"
        else:
            if resp.status_code == 200:
                return _extract_content(resp)
            if resp.status_code not in RETRYABLE_STATUS:
                # Never log headers: they contain the API key.
                logger.error("LLM rejected request: HTTP %s %s", resp.status_code, resp.text[:300])
                raise LLMError(f"LLM rejected the request (HTTP {resp.status_code})")
            problem = f"HTTP {resp.status_code}"

        if attempt < settings.LLM_MAX_ATTEMPTS:
            delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.5)
            logger.warning("LLM attempt %s failed (%s); retrying in %.1fs", attempt, problem, delay)
            sleep(delay)

    raise LLMUnavailableError(
        f"LLM unavailable after {settings.LLM_MAX_ATTEMPTS} attempts ({problem})"
    )


def _extract_content(resp: httpx.Response) -> str:
    try:
        choice = resp.json()["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("Unexpected response shape from LLM") from exc
    # Empty or missing content is returned as "" so the caller treats it as bad OUTPUT
    # (and asks again) rather than as a broken connection.
    return content if isinstance(content, str) else ""
