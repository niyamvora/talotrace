"""HR API. require_hr sits on the router, so every route here (and every route added later) needs sign-in."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import HrUser, require_hr
from app.config import settings
from app.db import get_db
from app.models import Answer, Candidate, Role, Score, ScoringJob

router = APIRouter(prefix="/api/hr", tags=["hr"], dependencies=[Depends(require_hr)])

Status = Literal["queued", "running", "scored", "failed", "needs_person"]
STATUSES: tuple[Status, ...] = ("queued", "running", "scored", "failed", "needs_person")


class AnswerOut(BaseModel):
    id: int
    question_id: str
    question_text: str
    kind: Literal["text", "audio"]
    text: str | None
    duration_seconds: int | None
    submitted_at: datetime
    is_current: bool  # False = superseded, does not count
    status: Status | None  # None only for a superseded answer that never got a job
    attempts: int
    last_error: str | None
    needs_person_reason: str | None
    ai_score: int | None
    ai_reason: str | None
    evidence_quote: str | None
    hr_score: int | None
    hr_reason: str | None
    hr_by: str | None
    hr_at: datetime | None


class CandidateOut(BaseModel):
    id: str
    name: str
    email: str
    access_token: str  # HR copies the candidate's /i/{token} link from this
    answers: list[AnswerOut]


class RoleRef(BaseModel):
    id: int
    name: str


class RoleSummary(RoleRef):
    candidates: int
    counts: dict[Status, int]  # jobs of current answers, by status


class RoleCandidates(BaseModel):
    role: RoleRef
    candidates: list[CandidateOut]


class Override(BaseModel):
    score: int = Field(ge=1, le=4)
    reason: str = Field(max_length=2000)


def answer_out(a: Answer) -> AnswerOut:
    job, score = a.job, a.score
    # The AI suggestion is shown only for a scored job: a failed or needs-a-person answer never shows a number.
    ai = score if job and job.status == "scored" else None
    return AnswerOut(
        id=a.id,
        question_id=a.question_id,
        question_text=a.question.text,
        kind=a.kind,
        text=a.text,
        duration_seconds=a.duration_seconds,
        submitted_at=a.submitted_at,
        is_current=a.is_current,
        status=job and job.status,
        attempts=job.attempts if job else 0,
        last_error=job and job.last_error,
        needs_person_reason=job and job.needs_person_reason,
        ai_score=ai and ai.ai_score,
        ai_reason=ai and ai.ai_reason,
        evidence_quote=ai and ai.evidence_quote,
        hr_score=score and score.hr_score,
        hr_reason=score and score.hr_reason,
        hr_by=score and score.hr_by,
        hr_at=score and score.hr_at,
    )


def get_answer(db: Session, answer_id: int) -> Answer:
    # Row lock: an override, a retry and the worker never write the same answer at once.
    answer = db.scalar(select(Answer).where(Answer.id == answer_id).with_for_update())
    if not answer:
        raise HTTPException(404, "Answer not found")
    return answer


@router.get("/me")
def me(user: HrUser = Depends(require_hr)) -> HrUser:
    return user


@router.get("/roles")
def roles(db: Session = Depends(get_db)) -> list[RoleSummary]:
    candidates = dict(db.execute(select(Candidate.role_id, func.count()).group_by(Candidate.role_id)).all())
    counts = {}
    for role_id, status, n in db.execute(
        select(Candidate.role_id, ScoringJob.status, func.count())
        .join(Answer, Answer.candidate_id == Candidate.id)
        .join(ScoringJob, ScoringJob.answer_id == Answer.id)
        .where(Answer.is_current)
        .group_by(Candidate.role_id, ScoringJob.status)
    ):
        counts.setdefault(role_id, dict.fromkeys(STATUSES, 0))[status] = n
    return [
        RoleSummary(
            id=r.id, name=r.name, candidates=candidates.get(r.id, 0), counts=counts.get(r.id, dict.fromkeys(STATUSES, 0))
        )
        for r in db.scalars(select(Role).order_by(Role.id))
    ]


@router.get("/roles/{role_id}/candidates")
def role_candidates(role_id: int, db: Session = Depends(get_db)) -> RoleCandidates:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    candidates = db.scalars(
        select(Candidate)
        .where(Candidate.role_id == role_id)
        .order_by(Candidate.id)
        .options(
            selectinload(Candidate.answers).options(
                selectinload(Answer.question), selectinload(Answer.job), selectinload(Answer.score)
            )
        )
    )
    return RoleCandidates(
        role=RoleRef(id=role.id, name=role.name),
        candidates=[
            CandidateOut(
                id=c.id,
                name=c.name,
                email=c.email,
                access_token=c.access_token,
                answers=[
                    answer_out(a)
                    for a in sorted(c.answers, key=lambda a: (int(a.question_id[1:]), a.submitted_at))
                ],
            )
            for c in candidates
        ],
    )


@router.post("/answers/{answer_id}/override")
def override(answer_id: int, body: Override, user: HrUser = Depends(require_hr), db: Session = Depends(get_db)) -> AnswerOut:
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(422, "A reason is required to override a score")
    answer = get_answer(db, answer_id)
    if not answer.is_current:
        raise HTTPException(409, "This answer was superseded by a newer one; override the answer that counts")
    score = answer.score or Score(answer_id=answer.id)
    score.hr_score, score.hr_reason, score.hr_by, score.hr_at = body.score, reason, user.email, datetime.now(UTC)
    answer.score = score
    db.commit()
    return answer_out(answer)


@router.post("/jobs/{answer_id}/retry")
def retry(answer_id: int, db: Session = Depends(get_db)) -> AnswerOut:
    answer = get_answer(db, answer_id)
    job = answer.job
    if not answer.is_current or not job or job.status not in ("failed", "needs_person"):
        raise HTTPException(409, "Only a failed or needs-a-person answer that counts can be retried")
    job.status, job.attempts, job.last_error, job.needs_person_reason, job.locked_at = "queued", 0, None, None, None
    db.commit()
    return answer_out(answer)


@router.get("/answers/{answer_id}/audio")
def audio(answer_id: int, db: Session = Depends(get_db)) -> FileResponse:
    answer = db.get(Answer, answer_id)
    path = settings.uploads_dir / answer.audio_path if answer and answer.audio_path else None
    if not path or not path.resolve().is_relative_to(settings.uploads_dir.resolve()) or not path.is_file():
        raise HTTPException(404, "No audio for this answer")
    # Python maps .m4a to audio/mp4a-latm, which <audio> elements may refuse; audio/mp4 always plays.
    return FileResponse(path, media_type="audio/mp4" if path.suffix == ".m4a" else None)
