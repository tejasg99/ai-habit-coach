import pytest
from sqlalchemy import func, select

from app.models.push_token import PushToken
from tests.helpers import bearer

TOKEN = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"


def register_token(client, headers, token=TOKEN):
    return client.post("/notifications/register-token", json={"token": token}, headers=headers)


def stored(session_factory):
    with session_factory() as db:
        return db.execute(select(PushToken.token, PushToken.user_id)).all()


def test_requires_auth(client):
    assert client.post("/notifications/register-token", json={"token": TOKEN}).status_code == 401


def test_register_stores_the_token(client, session_factory, headers):
    assert register_token(client, headers).status_code == 204
    assert [t for t, _ in stored(session_factory)] == [TOKEN]


def test_registering_twice_keeps_one_row(client, session_factory, headers):
    register_token(client, headers)
    assert register_token(client, headers).status_code == 204
    assert len(stored(session_factory)) == 1


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "abc",
        "ExponentPushToken[]",
        "ExponentPushToken[has space]",
        "ExponentPushToken[unterminated",
        "ExponentPushToken[" + "a" * 300 + "]",
    ],
)
def test_malformed_tokens_are_rejected(client, headers, bad):
    assert register_token(client, headers, bad).status_code == 422


def test_unknown_fields_are_rejected(client, headers):
    res = client.post(
        "/notifications/register-token", json={"token": TOKEN, "user_id": 99}, headers=headers
    )
    assert res.status_code == 422


def test_a_token_moves_to_whoever_registers_it_last(client, session_factory, headers, register):
    register_token(client, headers)  # first user's phone...
    bob = bearer(register("bob@example.com"))
    bob_id = client.get("/users/me", headers=bob).json()["id"]
    register_token(client, bob)  # ...is now used by Bob
    assert stored(session_factory) == [(TOKEN, bob_id)]


def test_you_can_only_unregister_your_own_token(client, session_factory, headers, register):
    register_token(client, headers)
    bob = bearer(register("bob@example.com"))
    body = {"token": TOKEN}

    assert client.post("/notifications/unregister-token", json=body, headers=bob).status_code == 204
    assert len(stored(session_factory)) == 1  # Bob's call changed nothing

    assert (
        client.post("/notifications/unregister-token", json=body, headers=headers).status_code
        == 204
    )
    assert stored(session_factory) == []
    assert (
        client.post("/notifications/unregister-token", json=body, headers=headers).status_code
        == 204
    )


def test_deleting_the_account_removes_its_tokens(client, session_factory, headers):
    register_token(client, headers)
    assert client.delete("/users/me", headers=headers).status_code == 204
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PushToken)) == 0
