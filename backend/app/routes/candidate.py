"""Candidate API. Response schemas here never carry a score, reason or status."""

import re
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Answer, Candidate, Question, ScoringJob, initial_job

router = APIRouter(prefix="/api/interview/{token}", tags=["candidate"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024
IdempotencyKey = Annotated[str, Header(min_length=1, max_length=100)]


class CurrentQuestion(BaseModel):
    id: str
    number: int
    text: str


class Interview(BaseModel):
    role: str
    total: int
    answered: int
    done: bool
    question: CurrentQuestion | None  # the first question without an answer; None when done


class TextAnswer(BaseModel):
    question_id: str
    text: str = Field(max_length=20_000)


class Receipt(BaseModel):
    answer_id: int
    received_at: datetime


def get_candidate(token: str, db: Session = Depends(get_db)) -> Candidate:
    candidate = db.scalar(select(Candidate).where(Candidate.access_token == token))
    if not candidate:
        raise HTTPException(404, "Interview not found")
    return candidate


@router.get("")
def interview(candidate: Candidate = Depends(get_candidate), db: Session = Depends(get_db)) -> Interview:
    questions = sorted(db.scalars(select(Question)), key=lambda q: int(q.id[1:]))  # Q2 before Q10
    answered = set(db.scalars(select(Answer.question_id).where(Answer.candidate_id == candidate.id, Answer.is_current)))
    number, question = next(((n, q) for n, q in enumerate(questions, 1) if q.id not in answered), (0, None))
    return Interview(
        role=candidate.role.name,
        total=len(questions),
        answered=len(answered),
        done=question is None,
        question=question and CurrentQuestion(id=question.id, number=number, text=question.text),
    )


@router.post("/answers")
def submit_text(
    body: TextAnswer,
    idempotency_key: IdempotencyKey,
    candidate: Candidate = Depends(get_candidate),
    db: Session = Depends(get_db),
) -> Receipt:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "The answer is empty")
    return submit(db, candidate, idempotency_key, body.question_id, lambda: Answer(kind="text", text=text))


@router.post("/answers/audio")
def submit_audio(
    question_id: Annotated[str, Form()],
    file: UploadFile,
    idempotency_key: IdempotencyKey,
    candidate: Candidate = Depends(get_candidate),
    db: Session = Depends(get_db),
) -> Receipt:
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(415, "Please upload an audio file")
    data = file.file.read(MAX_AUDIO_BYTES + 1)  # ponytail: holds up to 25 MB in memory per upload
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "The audio file is larger than 25 MB")
    if not data:
        raise HTTPException(422, "The audio file is empty")

    def store() -> Answer:
        # Our own file name: never trust the client's name as a path.
        suffix = Path(file.filename or "").suffix.lower()
        name = uuid.uuid4().hex + (suffix if re.fullmatch(r"\.[a-z0-9]{1,5}", suffix) else "")
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        (settings.uploads_dir / name).write_bytes(data)
        return Answer(kind="audio", audio_path=name)

    return submit(db, candidate, idempotency_key, question_id, store)


def submit(db: Session, candidate: Candidate, key: str, question_id: str, make_answer: Callable[[], Answer]) -> Receipt:
    """Save one answer and its job in one transaction. The same key always returns the same receipt."""
    # Serialize this candidate's submissions: a double click or two tabs wait here instead of racing.
    db.execute(select(Candidate.id).where(Candidate.id == candidate.id).with_for_update())

    existing = db.scalar(select(Answer).where(Answer.candidate_id == candidate.id, Answer.idempotency_key == key))
    if existing:
        return Receipt(answer_id=existing.id, received_at=existing.submitted_at)
    if not db.get(Question, question_id):
        raise HTTPException(422, "Unknown question")

    previous = db.scalar(
        select(Answer).where(Answer.candidate_id == candidate.id, Answer.question_id == question_id, Answer.is_current)
    )
    if previous:
        previous.is_current = False
        # Only a job nobody has picked up yet is cancelled. A running one finishes, and HR sees it as superseded.
        db.execute(delete(ScoringJob).where(ScoringJob.answer_id == previous.id, ScoringJob.status == "queued"))
        db.flush()  # the old answer must stop counting before the new one is inserted

    answer = make_answer()  # only runs for a new submission (writes the audio file)
    answer.candidate_id, answer.question_id, answer.idempotency_key = candidate.id, question_id, key
    answer.job = initial_job(answer)
    db.add(answer)
    db.commit()
    return Receipt(answer_id=answer.id, received_at=answer.submitted_at)
