from fastapi.testclient import TestClient

from app.main import app


def test_health_reaches_the_database():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"ok": True}
