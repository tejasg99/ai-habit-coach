def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_db(client):
    assert client.get("/health/db").status_code == 200
