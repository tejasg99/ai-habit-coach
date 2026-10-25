import json

import httpx
import pytest

from app.core.config import settings
from app.services.llm_client import LLMError, LLMUnavailableError, chat_completion

MESSAGES = [{"role": "user", "content": "hi"}]


def ok_body(content="hello"):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_returns_message_content():
    client = client_for(lambda request: httpx.Response(200, json=ok_body("hi there")))
    assert chat_completion(MESSAGES, http_client=client, sleep=lambda s: None) == "hi there"


def test_request_has_model_json_mode_key_and_correct_url():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json=ok_body())

    chat_completion(MESSAGES, http_client=client_for(handler), sleep=lambda s: None)
    assert seen["auth"] == "Bearer test-key-not-real"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["url"] == "http://llm.invalid/v1/chat/completions"


def test_retries_transient_errors_then_succeeds():
    queue = [httpx.Response(503), httpx.Response(429), httpx.Response(200, json=ok_body("finally"))]
    sleeps = []
    client = client_for(lambda request: queue.pop(0))
    assert chat_completion(MESSAGES, http_client=client, sleep=sleeps.append) == "finally"
    assert len(sleeps) == 2 and all(s > 0 for s in sleeps)


def test_timeouts_are_retried():
    queue = [httpx.ReadTimeout("slow"), httpx.Response(200, json=ok_body("ok"))]

    def handler(request):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    assert chat_completion(MESSAGES, http_client=client_for(handler), sleep=lambda s: None) == "ok"


def test_gives_up_after_max_attempts():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(LLMUnavailableError):
        chat_completion(MESSAGES, http_client=client_for(handler), sleep=sleeps.append)
    assert len(calls) == settings.LLM_MAX_ATTEMPTS
    assert len(sleeps) == settings.LLM_MAX_ATTEMPTS - 1  # no pointless wait after the last try


def test_auth_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(LLMError) as exc_info:
        chat_completion(MESSAGES, http_client=client_for(handler), sleep=lambda s: None)
    assert not isinstance(exc_info.value, LLMUnavailableError)
    assert len(calls) == 1


def test_unexpected_response_shape_raises():
    client = client_for(lambda request: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(LLMError):
        chat_completion(MESSAGES, http_client=client, sleep=lambda s: None)


def test_empty_content_is_returned_as_empty_string():
    client = client_for(lambda request: httpx.Response(200, json=ok_body(None)))
    assert chat_completion(MESSAGES, http_client=client, sleep=lambda s: None) == ""
