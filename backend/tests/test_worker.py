from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.models import Answer, Score, ScoringJob
from app.scorer import ScoreOut
from app.seed import seed
from app.worker import run_once

A001_QUOTE = "I designed an idempotency key for each charge"  # word for word from data/answers/A001.json


class FakeClient:
    """Stands in for anthropic.Anthropic: returns (or raises) the queued outcomes in order."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []
        self.beta = self.messages = self

    def parse(self, **request):
        self.calls.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def reply(stop_reason="end_turn", **fields):
    out = {"score": 3, "reason": "Clear personal part and a checkable result.", "evidence_quote": A001_QUOTE,
           "injection_attempt": False, "needs_person": False, "needs_person_reason": ""} | fields  # fmt: skip
    # model_construct skips validation, so a fake can return what a misbehaving model might
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=ScoreOut.model_construct(**out), model="claude-opus-5-5")


@pytest.fixture
def a001(db, tmp_path):
    """Seeded pack with only A001's job left in the queue."""
    seed(db, settings.data_dir, tmp_path)
    answer = db.scalar(select(Answer).where(Answer.idempotency_key == "A001"))
    db.execute(delete(ScoringJob).where(ScoringJob.answer_id != answer.id))
    db.flush()
    return answer


def result(db, answer):
    db.expire_all()
    return db.get(ScoringJob, answer.id), db.get(Score, answer.id)


def test_a_valid_score_is_stored_with_its_reason(db, a001):
    client = FakeClient(reply())
    assert run_once(db, client) and not run_once(db, client)  # one job, then an empty queue
    job, score = result(db, a001)
    assert (job.status, job.attempts, job.locked_at) == ("scored", 1, None)
    assert (score.ai_score, score.evidence_quote, score.model) == (3, A001_QUOTE, "claude-opus-5-5")

    request = client.calls[0]
    assert "Grading guide:" in request["system"] and a001.text not in request["system"]
    assert request["messages"][0]["content"].startswith("<answer>")  # the answer is data, not instructions


@pytest.mark.parametrize(
    "bad",
    [
        reply(score=7),
        reply(reason="  "),
        reply(evidence_quote="a sentence the candidate never said"),
        anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")),
    ],
    ids=["score-out-of-range", "empty-reason", "invented-quote", "api-timeout"],
)
def test_bad_output_or_api_errors_fail_without_a_score(db, a001, bad):
    run_once(db, FakeClient(bad))
    job, score = result(db, a001)
    assert job.status == "failed" and job.last_error and score is None


def test_injection_goes_to_a_person_never_to_a_score(db, a001):
    run_once(db, FakeClient(reply(score=4, injection_attempt=True)))
    job, _ = result(db, a001)
    assert job.status == "needs_person" and "prompt injection" in job.needs_person_reason


def test_refusal_or_cut_off_output_goes_to_a_person(db, a001):
    run_once(db, FakeClient(reply(stop_reason="refusal")))
    assert result(db, a001)[0].status == "needs_person"


def test_empty_or_audio_answers_never_reach_the_model(db, a001):
    a001.text = "   "
    db.flush()
    client = FakeClient()
    run_once(db, client)
    assert client.calls == [] and result(db, a001)[0].needs_person_reason == "empty answer"


def test_a_crashed_workers_job_is_requeued_and_scored(db, a001):
    a001.job.status, a001.job.locked_at, a001.job.attempts = "running", datetime.now(UTC) - timedelta(hours=1), 1
    db.flush()
    run_once(db, FakeClient(reply()))
    job, _ = result(db, a001)
    assert (job.status, job.attempts) == ("scored", 2)
