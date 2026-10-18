from tests.helpers import bearer


def test_signup_normalizes_email_and_hides_password(client):
    res = client.post(
        "/auth/signup", json={"email": "Tejas@Example.com", "password": "correct-horse-battery"}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "tejas@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_duplicate_email_is_rejected_case_insensitively(client, register):
    register("tejas@example.com")
    res = client.post(
        "/auth/signup", json={"email": "TEJAS@example.com", "password": "another-password-1"}
    )
    assert res.status_code == 409


def test_short_password_is_rejected(client):
    res = client.post("/auth/signup", json={"email": "a@example.com", "password": "short"})
    assert res.status_code == 422


def test_wrong_password_and_unknown_email_look_identical(client, register):
    register("tejas@example.com", "correct-horse-battery")
    wrong_pw = client.post(
        "/auth/login", data={"username": "ghost@example.com", "password": "not-the-password"}
    )
    unknown = client.post(
        "/auth/login", data={"username": "ghost@example.com", "password": "whatever-123"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_protected_route_required_token(client):
    assert client.get("/user/me").status_code == 401


def test_me_with_valid_token(client, register):
    tokens = register()
    res = client.get("/users/me", headers=bearer(tokens))
    assert res.status_code == 200
    assert res.json()["email"] == "tejas@example.com"


def test_tampered_token_is_rejected(client, register):
    tokens = register()
    forged = tokens["access_token"][:-5] + "AAAAA"
    res = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_refresh_issues_working_tokens(client, register):
    tokens = register()
    res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    assert client.get("/users/me", headers=bearer(res.json())).status_code == 200


def test_access_token_cannot_refresh(client, register):
    tokens = register()
    res = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert res.status_code == 401


def test_refresh_token_cannot_authenticate_requests(client, register):
    tokens = register()
    res = client.get("/users/me", headers=bearer(tokens, "refresh_token"))
    assert res.status_code == 401
