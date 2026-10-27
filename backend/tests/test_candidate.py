import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Answer, Candidate, ScoringJob
from app.seed import seed


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", tmp_path)
    seed(db, settings.data_dir, tmp_path)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def url(db):
    return f"/api/interview/{db.get(Candidate, 'DEMO1').access_token}"


def answer_text(client, url, key, text="I fixed the double-charge bug.", question_id="Q1"):
    return client.post(f"{url}/answers", json={"question_id": question_id, "text": text}, headers={"Idempotency-Key": key})


def test_unknown_token_is_404(client):
    assert client.get("/api/interview/not-a-token").status_code == 404


def test_interview_shows_the_next_question_and_no_grades(client, url):
    first = client.get(url).json()
    assert first.keys() == {"role", "total", "answered", "done", "question"}
    assert first["question"]["number"] == 1 and first["total"] == 6 and not first["done"]

    answer_text(client, url, "k1")
    assert client.get(url).json()["question"] | {"text": ""} == {"id": "Q2", "number": 2, "text": ""}


def test_same_key_twice_is_one_answer_and_one_job(client, db, url):
    first, again = answer_text(client, url, "k1"), answer_text(client, url, "k1")
    assert first.status_code == 200 and again.json() == first.json()
    assert first.json().keys() == {"answer_id", "received_at"}
    assert db.scalar(select(func.count()).select_from(Answer).where(Answer.candidate_id == "DEMO1")) == 1
    jobs = select(func.count()).select_from(ScoringJob).join(Answer).where(Answer.candidate_id == "DEMO1")
    assert db.scalar(jobs) == 1


def test_a_token_only_ever_sees_its_own_interview(client, db, url):
    other = f"/api/interview/{db.get(Candidate, 'DEMO2').access_token}"
    mine = answer_text(client, url, "k1").json()

    me, them = client.get(url).json(), client.get(other).json()
    assert (me["role"], me["answered"]) == ("Backend Engineer", 1)
    assert (them["role"], them["answered"]) == ("Sales Executive", 0)  # DEMO1's answer is invisible here
    # The same key under another token is that candidate's own submission, never DEMO1's receipt.
    assert answer_text(client, other, "k1").json()["answer_id"] != mine["answer_id"]


def test_a_new_answer_supersedes_the_old_one(client, db, url):
    old = answer_text(client, url, "k1", text="draft").json()["answer_id"]
    new = answer_text(client, url, "k2", text="final").json()["answer_id"]
    db.expire_all()
    assert not db.get(Answer, old).is_current and db.get(ScoringJob, old) is None  # queued job cancelled
    assert db.get(Answer, new).is_current and db.get(ScoringJob, new).status == "queued"


def test_bad_text_answers_are_rejected(client, url):
    assert answer_text(client, url, "k1", text="   ").status_code == 422
    assert answer_text(client, url, "k1", question_id="Q99").status_code == 422
    assert client.post(f"{url}/answers", json={"question_id": "Q1", "text": "hi"}).status_code == 422  # no key


def test_audio_is_stored_and_goes_to_a_person(client, db, url, tmp_path):
    def upload(name, content_type, key="a1"):
        files = {"file": (name, b"fake-audio", content_type)}
        return client.post(f"{url}/answers/audio", data={"question_id": "Q1"}, files=files, headers={"Idempotency-Key": key})

    assert upload("notes.txt", "text/plain").status_code == 415
    receipt = upload("../../evil.m4a", "audio/mp4").json()
    a = db.get(Answer, receipt["answer_id"])
    assert a.kind == "audio" and "/" not in a.audio_path and a.audio_path.endswith(".m4a")
    assert (tmp_path / a.audio_path).read_bytes() == b"fake-audio"
    assert a.job.status == "needs_person"
    files_before = len(list(tmp_path.iterdir()))
    assert upload("again.m4a", "audio/mp4").json() == receipt  # same key, same receipt
    assert len(list(tmp_path.iterdir())) == files_before  # and no second file
