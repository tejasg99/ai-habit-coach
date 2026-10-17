from tests.helpers import bearer


def test_patch_display_name_is_stripped(client, register):
    headers = bearer(register())
    res = client.patch("/users/me", json={"display_name": "  Tejas G  "}, headers=headers)
    assert res.status_code == 200
    assert res.json()["display_name"] == "Tejas G"


def test_blank_display_name_clears_it(client, register):
    headers = bearer(register())
    client.patch("/users/me", json={"display_name": "Tejas"}, headers=headers)
    res = client.patch("/users/me", json={"display_name": "   "}, headers=headers)
    assert res.json()["display_name"] is None


def test_empty_patch_changes_nothing(client, register):
    headers = bearer(register())
    client.patch("/users/me", json={"display_name": "Tejas"}, headers=headers)
    res = client.patch("/users/me", json={}, headers=headers)
    assert res.status_code == 200
    assert res.json()["display_name"] == "Tejas"


def test_patch_cannot_change_email(client, register):
    headers = bearer(register())
    res = client.patch("/users/me", json={"email": "hacker@example.com"}, headers=headers)
    assert res.status_code == 422
    assert client.get("/users/me", headers=headers).json()["email"] == "tejas@example.com"


def test_delete_account(client, register):
    tokens = register()
    assert client.delete("/users/me", headers=bearer(tokens)).status_code == 204
    # The old token is still validly signed, but the user no longer exists.
    assert client.get("/users/me", headers=bearer(tokens)).status_code == 401
    res = client.post(
        "/auth/login", data={"username": "tejas@example.com", "password": "correct-horse-battery"}
    )
    assert res.status_code == 401