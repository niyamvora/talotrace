from fastapi.testclient import TestClient

from app.main import app


def test_mock_sign_in_gates_every_hr_route():
    with TestClient(app) as client:
        assert client.get("/api/hr/me").status_code == 401
        client.cookies.set("talotrace_hr", "forged.cookie")
        assert client.get("/api/hr/me").status_code == 401

        assert client.post("/api/hr/login", json={"provider": "myspace", "email": "hr@talotrace.ai"}).status_code == 422
        assert client.post("/api/hr/login", json={"provider": "google", "email": "not-an-email"}).status_code == 422

        r = client.post("/api/hr/login", json={"provider": "google", "email": "hr@talotrace.ai"})
        assert r.status_code == 200 and "httponly" in r.headers["set-cookie"].lower()
        assert client.get("/api/hr/me").json() == {"provider": "google", "email": "hr@talotrace.ai"}

        assert client.post("/api/hr/logout").status_code == 204
        assert client.get("/api/hr/me").status_code == 401
