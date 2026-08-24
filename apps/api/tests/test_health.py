"""Health endpoint tests."""


def test_health_reports_ok_and_db_up(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]
    assert body["environment"] == "test"
