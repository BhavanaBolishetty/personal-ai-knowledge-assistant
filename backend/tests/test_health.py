from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_reports_status_and_database_fields():
    response = client.get("/health")
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert "database" in body
