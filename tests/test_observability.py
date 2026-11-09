import logging
import re

HEX_ID = r"[0-9a-f]{32}"


def test_every_response_carries_a_request_id(client):
    assert re.fullmatch(HEX_ID, client.get("/health").headers["x-request-id"])


def test_a_safe_client_supplied_id_is_echoed(client):
    res = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert res.headers["x-request-id"] == "trace-abc-12345"


def test_an_unsafe_client_supplied_id_is_replaced(client):
    res = client.get("/health", headers={"X-Request-ID": "bad id with spaces!"})
    assert re.fullmatch(HEX_ID, res.headers["x-request-id"])


def test_access_log_lines_carry_the_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        res = client.get("/users/me")  # a 401 is still logged
    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    assert records[0].request_id == res.headers["x-request-id"]
    assert "GET /users/me -> 401" in records[0].getMessage()


def test_health_checks_are_not_logged_at_info(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/health")
    assert [r for r in caplog.records if r.name == "app.access"] == []


def test_logs_never_contain_credentials(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/auth/login", data={"username": "a@example.com", "password": "super-secret-pw-123"}
        )
        client.get("/users/me", headers={"Authorization": "Bearer abc.def.ghi-secret"})
    assert "super-secret-pw-123" not in caplog.text
    assert "abc.def.ghi-secret" not in caplog.text
