import json

import httpx
import pytest

from app.core.config import settings
from app.services.expo_push import (
    MAX_ATTEMPTS,
    PushError,
    PushMessage,
    PushUnavailableError,
    send_push,
)

TOKEN_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOKEN_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"
TOKEN_C = "ExponentPushToken[cccccccccccccccccccccc]"

OK = {"status": "ok", "id": "ticket-1"}
DEAD = {"status": "error", "message": "not registered", "details": {"error": "DeviceNotRegistered"}}
TOO_BIG = {"status": "error", "message": "too big", "details": {"error": "MessageTooBig"}}


def msg(token=TOKEN_A):
    return PushMessage(to=token, title="Hi", body="There")


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def tickets(*items):
    return httpx.Response(200, json={"data": list(items)})


def send(messages, handler):
    return send_push(messages, http_client=client_for(handler), sleep=lambda s: None)


def test_results_follow_message_order():
    results = send([msg(TOKEN_A), msg(TOKEN_B), msg(TOKEN_C)], lambda r: tickets(OK, DEAD, TOO_BIG))
    assert [(r.token, r.status) for r in results] == [
        (TOKEN_A, "ok"),
        (TOKEN_B, "invalid_token"),
        (TOKEN_C, "failed"),
    ]
    assert results[2].detail == "MessageTooBig"


def test_request_shape():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return tickets(OK)

    send([PushMessage(to=TOKEN_A, title="T", body="B", data={"screen": "today"})], handler)
    assert seen["url"] == "http://expo.invalid/push"
    assert seen["auth"] is None
    assert seen["body"] == [
        {"to": TOKEN_A, "title": "T", "body": "B", "sound": "default", "data": {"screen": "today"}}
    ]


def test_access_token_is_sent_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", "secret-token")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        return tickets(OK)

    send([msg()], handler)
    assert seen["auth"] == "Bearer secret-token"


def test_transient_errors_are_retried():
    queue = [httpx.Response(503), httpx.Response(429), tickets(OK)]
    assert send([msg()], lambda r: queue.pop(0))[0].status == "ok"


def test_timeouts_are_retried():
    queue = [httpx.ReadTimeout("slow"), tickets(OK)]

    def handler(request):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    assert send([msg()], handler)[0].status == "ok"


def test_gives_up_after_max_attempts():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(PushUnavailableError):
        send([msg()], handler)
    assert len(calls) == MAX_ATTEMPTS


def test_rejected_requests_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"errors": [{"message": "bad token"}]})

    with pytest.raises(PushError) as exc_info:
        send([msg()], handler)
    assert not isinstance(exc_info.value, PushUnavailableError)
    assert len(calls) == 1


def test_a_ticket_count_mismatch_is_an_error():
    with pytest.raises(PushError):
        send([msg(TOKEN_A), msg(TOKEN_B)], lambda r: tickets(OK))


def test_no_messages_means_no_request():
    calls = []
    assert send([], lambda r: calls.append(1)) == []
    assert calls == []


def test_more_than_one_batch_is_refused():
    with pytest.raises(ValueError):
        send([msg()] * 101, lambda r: tickets(OK))
