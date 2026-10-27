"""`python -m app.worker`: scores queued answers one at a time until stopped (Ctrl+C finishes the current one).

- Claim: the oldest queued job, FOR UPDATE SKIP LOCKED, so several workers never take the same job.
- The model call runs with no database lock held. The result is written in one transaction,
  under the same answer-row lock HR's override and retry take.
- A job left "running" by a crashed worker goes back to the queue after STALE_AFTER.
"""

import logging
import signal
from datetime import UTC, datetime, timedelta
from threading import Event

import anthropic
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Answer, Score, ScoringJob, person_reason
from app.scorer import Verdict, score_answer

STALE_AFTER = timedelta(minutes=10)  # longer than the worst model call: 3 tries x 90 s timeout + backoff
MAX_CLAIMS = 3  # a job that keeps crashing its worker stops after this many claims
IDLE_SECONDS = 2

log = logging.getLogger("worker")


def run_once(db: Session, client: anthropic.Anthropic) -> bool:
    """Claim and finish one job. Returns False when there is nothing queued."""
    db.execute(
        update(ScoringJob)
        .where(ScoringJob.status == "running", ScoringJob.locked_at < datetime.now(UTC) - STALE_AFTER)
        .values(status="queued", locked_at=None)
    )
    job = db.scalar(
        select(ScoringJob)
        .where(ScoringJob.status == "queued")
        .order_by(ScoringJob.created_at, ScoringJob.answer_id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if not job:
        db.commit()
        return False

    job.attempts += 1
    if job.attempts > MAX_CLAIMS:
        job.status, job.last_error = "failed", f"stopped after {MAX_CLAIMS} attempts"
        db.commit()
        return True
    claimed_at = datetime.now(UTC)
    job.status, job.locked_at = "running", claimed_at
    answer = job.answer
    answer_id, reason = answer.id, person_reason(answer)
    prompt = dict(role=answer.candidate.role.name, question=answer.question.text, rubric=answer.question.rubric, answer=answer.text)
    db.commit()  # the claim is visible now, and no lock is held during the model call

    verdict = Verdict("needs_person", reason=reason) if reason else score_answer(client, **prompt)

    db.expire_all()
    answer = db.scalar(select(Answer).where(Answer.id == answer_id).with_for_update())
    job = answer.job
    if not job or job.status != "running" or job.locked_at != claimed_at:
        db.rollback()  # another worker re-claimed it after we went stale; its result wins
        return True
    job.status, job.locked_at = verdict.status, None
    job.last_error = verdict.reason if verdict.status == "failed" else None
    job.needs_person_reason = verdict.reason if verdict.status == "needs_person" else None
    if verdict.out:
        score = answer.score or Score(answer_id=answer.id)  # keeps any HR override already there
        score.ai_score, score.ai_reason, score.evidence_quote = verdict.out.score, verdict.out.reason, verdict.out.evidence_quote
        score.model, score.scored_at = verdict.model, datetime.now(UTC)
        answer.score = score
    db.commit()
    log.info("answer %s (%s): %s %s", answer_id, answer.idempotency_key, verdict.status, verdict.out.score if verdict.out else verdict.reason)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # one line per job is enough
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in backend/.env")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=90, max_retries=2)
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: (log.info("stopping after the current answer"), stop.set()))

    Base.metadata.create_all(engine)
    log.info("worker started, model %s", settings.scorer_model)
    with SessionLocal() as db:
        while not stop.is_set():
            if not run_once(db, client):
                stop.wait(IDLE_SECONDS)


if __name__ == "__main__":
    main()
