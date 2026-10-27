from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Answer, Candidate, Question, Role, Score, ScoringJob

NOW = datetime.now(UTC)


@pytest.fixture
def candidate(db):
    role = Role(name="Backend Engineer")
    db.add(Question(id="Q1", text="A piece of work you are proud of?", rubric="1: ... 4: ..."))
    db.add(Candidate(id="C1", role=role, name="Ada", email="ada@example.com", access_token="tok"))
    db.flush()
    return db.get(Candidate, "C1")


def answer(candidate, **overrides):
    fields = {"candidate_id": candidate.id, "question_id": "Q1", "kind": "text", "text": "hi", "idempotency_key": "k1"}
    return Answer(**(fields | overrides))


def saved(db, *objs):
    db.add_all(objs)
    db.flush()
    return objs[0]


def rejected(db, obj):
    # The savepoint keeps the rows created earlier in the test after the failed insert.
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(obj)
        db.flush()


def test_same_idempotency_key_is_one_submission(db, candidate):
    saved(db, answer(candidate, idempotency_key="k1", is_current=False))
    rejected(db, answer(candidate, idempotency_key="k1"))


def test_only_one_current_answer_per_question(db, candidate):
    saved(db, answer(candidate, idempotency_key="k1"), answer(candidate, idempotency_key="k2", is_current=False))
    rejected(db, answer(candidate, idempotency_key="k3"))


def test_answer_payload_matches_kind(db, candidate):
    rejected(db, answer(candidate, text=None))
    rejected(db, answer(candidate, kind="audio"))  # audio without a file
    rejected(db, answer(candidate, kind="video"))
    saved(db, answer(candidate, kind="audio", text=None, audio_path="A031.m4a"))


def test_job_status_must_be_known_and_explained(db, candidate):
    a = saved(db, answer(candidate))
    rejected(db, ScoringJob(answer_id=a.id, status="done"))
    rejected(db, ScoringJob(answer_id=a.id, status="failed"))
    rejected(db, ScoringJob(answer_id=a.id, status="needs_person"))
    saved(db, ScoringJob(answer_id=a.id, status="needs_person", needs_person_reason="empty answer"))


def test_scores_are_1_to_4_and_always_have_a_reason(db, candidate):
    a = saved(db, answer(candidate))
    hr = {"hr_by": "hr", "hr_at": NOW}
    rejected(db, Score(answer_id=a.id, ai_score=5, ai_reason="x"))
    rejected(db, Score(answer_id=a.id, ai_score=3))
    rejected(db, Score(answer_id=a.id, hr_score=2, **hr))  # NULL reason: the CHECK-passes-on-NULL trap
    rejected(db, Score(answer_id=a.id, hr_score=2, hr_reason="   ", **hr))
    rejected(db, Score(answer_id=a.id))
    saved(db, Score(answer_id=a.id, ai_score=3, ai_reason="clear part", hr_score=2, hr_reason="vague", **hr))
