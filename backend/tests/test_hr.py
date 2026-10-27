import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Answer, Role, Score
from app.seed import seed

ANSWER_KEYS = {
    "id", "question_id", "question_text", "kind", "text", "duration_seconds", "submitted_at", "is_current",
    "status", "attempts", "last_error", "needs_person_reason", "ai_score", "ai_reason", "evidence_quote",
    "hr_score", "hr_reason", "hr_by", "hr_at",
}  # fmt: skip


@pytest.fixture
def anon(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    seed(db, settings.data_dir, tmp_path)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def hr(anon):
    anon.post("/api/hr/login", json={"provider": "google", "email": "hr@talotrace.ai"})
    return anon


def pack(db, key):
    return db.scalar(select(Answer).where(Answer.idempotency_key == key))


def listed(hr, db, key):
    a = pack(db, key)
    candidates = hr.get(f"/api/hr/roles/{a.candidate.role_id}/candidates").json()["candidates"]
    return next(x for c in candidates for x in c["answers"] if x["id"] == a.id)


def test_every_hr_route_needs_sign_in(anon):
    hr_routes = [
        (method, path.replace("{role_id}", "1").replace("{answer_id}", "1"))
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/hr") and path not in ("/api/hr/login", "/api/hr/logout")
        for method in ops
    ]
    assert len(hr_routes) >= 6
    for method, path in hr_routes:
        assert anon.request(method, path).status_code == 401, f"{method} {path} is open"


def test_roles_count_current_answers_by_status(hr):
    roles = hr.get("/api/hr/roles").json()
    assert len(roles) == 5 and sum(r["candidates"] for r in roles) == 23
    assert sum(r["counts"]["queued"] for r in roles) == 28
    assert sum(r["counts"]["needs_person"] for r in roles) == 6


def test_answers_show_status_and_which_one_counts(hr, db):
    a007 = listed(hr, db, "A007")
    assert a007.keys() == ANSWER_KEYS
    assert a007["status"] == "needs_person" and a007["needs_person_reason"] == "empty answer"
    a022 = listed(hr, db, "A022")
    assert a022["is_current"] is False and a022["status"] is None
    assert listed(hr, db, "A023")["is_current"]


def test_a_failed_answer_never_shows_a_score(hr, db):
    a = pack(db, "A001")
    a.job.status, a.job.last_error = "failed", "API timeout"
    db.add(Score(answer_id=a.id, ai_score=1, ai_reason="stale suggestion"))
    db.flush()
    shown = listed(hr, db, "A001")
    assert shown["status"] == "failed" and shown["last_error"] == "API timeout"
    assert shown["ai_score"] is None and shown["ai_reason"] is None


def test_override_needs_a_reason_and_records_who(hr, db):
    url = f"/api/hr/answers/{pack(db, 'A001').id}/override"
    assert hr.post(url, json={"score": 3}).status_code == 422
    assert hr.post(url, json={"score": 3, "reason": "   "}).status_code == 422
    assert hr.post(url, json={"score": 5, "reason": "great"}).status_code == 422
    r = hr.post(url, json={"score": 2, "reason": "Personal part stays vague"}).json()
    assert (r["hr_score"], r["hr_reason"], r["hr_by"]) == (2, "Personal part stays vague", "hr@talotrace.ai")
    assert r["ai_score"] is None  # no AI score yet: the override stands on its own

    superseded = f"/api/hr/answers/{pack(db, 'A022').id}/override"
    assert hr.post(superseded, json={"score": 2, "reason": "x"}).status_code == 409


def test_retry_only_for_failed_or_needs_person(hr, db):
    a = pack(db, "A001")
    assert hr.post(f"/api/hr/jobs/{a.id}/retry").status_code == 409  # still queued
    a.job.status, a.job.last_error, a.job.attempts = "failed", "API timeout", 3
    db.flush()
    r = hr.post(f"/api/hr/jobs/{a.id}/retry").json()
    assert (r["status"], r["attempts"], r["last_error"]) == ("queued", 0, None)


def test_audio_is_served_to_hr_only_for_audio_answers(hr, db):
    r = hr.get(f"/api/hr/answers/{pack(db, 'A031').id}/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4" and r.content
    assert hr.get(f"/api/hr/answers/{pack(db, 'A001').id}/audio").status_code == 404
    assert hr.get("/api/hr/roles/999/candidates").status_code == 404
    assert db.scalar(select(Role).where(Role.name == "Backend Engineer"))
