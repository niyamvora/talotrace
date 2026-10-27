"""Tables and the constraints that keep the data honest.

The rules live in Postgres, not only in Python: a double submit, a second "current" answer,
a score outside 1-4 or an override without a reason is rejected by the database even if
the API code has a bug.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy import text as sql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "Q1".."Q6", as in questions.md
    text: Mapped[str] = mapped_column(Text)
    rubric: Mapped[str] = mapped_column(Text)  # the 1-4 grading guide


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # data pack id, e.g. "C2041"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    access_token: Mapped[str] = mapped_column(String(64), unique=True)  # the secret in the candidate's link

    role: Mapped[Role] = relationship()
    answers: Mapped[list["Answer"]] = relationship(back_populates="candidate")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        # Same Idempotency-Key from the same candidate = the same submission, never a second row.
        UniqueConstraint("candidate_id", "idempotency_key"),
        # Only one answer per candidate per question counts. Older ones stay, marked superseded.
        Index("uq_answers_one_current", "candidate_id", "question_id", unique=True, postgresql_where=sql("is_current")),
        CheckConstraint("kind IN ('text', 'audio')", name="kind"),
        CheckConstraint(
            "(kind = 'text' AND text IS NOT NULL) OR (kind = 'audio' AND audio_path IS NOT NULL)",
            name="payload_matches_kind",
        ),
        CheckConstraint("duration_seconds >= 0", name="duration_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    kind: Mapped[str] = mapped_column(String(8))
    text: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(String(255))  # relative to settings.uploads_dir
    duration_seconds: Mapped[int | None]
    idempotency_key: Mapped[str] = mapped_column(String(100))  # seeded rows use the pack id, e.g. "A001"
    is_current: Mapped[bool] = mapped_column(default=True)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    candidate: Mapped[Candidate] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
    job: Mapped["ScoringJob | None"] = relationship(back_populates="answer")
    score: Mapped["Score | None"] = relationship(back_populates="answer")


class ScoringJob(Base):
    """One job per answer: the answer id is the primary key. HR's four statuses come from here."""

    __tablename__ = "scoring_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'scored', 'failed', 'needs_person')", name="status"),
        # A job never sits in failed / needs_person without saying why.
        CheckConstraint("status <> 'failed' OR last_error IS NOT NULL", name="failed_has_error"),
        CheckConstraint("status <> 'needs_person' OR needs_person_reason IS NOT NULL", name="needs_person_has_reason"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )

    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    needs_person_reason: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None]  # set on claim; "running" jobs with an old locked_at get re-queued
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    answer: Mapped[Answer] = relationship(back_populates="job")


def initial_job(answer: Answer) -> ScoringJob:
    """The job a new answer starts with. Audio and empty answers go to a person, never to the model."""
    if answer.kind == "audio":
        return ScoringJob(status="needs_person", needs_person_reason="audio received, not transcribed")
    if not answer.text.strip():
        return ScoringJob(status="needs_person", needs_person_reason="empty answer")
    return ScoringJob(status="queued")


class Score(Base):
    """The AI suggestion and HR's decision for one answer. When HR has scored it, HR's score counts."""

    __tablename__ = "scores"
    __table_args__ = (
        CheckConstraint("ai_score BETWEEN 1 AND 4", name="ai_score_range"),
        CheckConstraint("hr_score BETWEEN 1 AND 4", name="hr_score_range"),
        # "IS NOT NULL AND" on purpose: a bare length(reason) > 0 is NULL for a NULL reason, and a
        # CHECK that evaluates to NULL passes.
        CheckConstraint(
            "ai_score IS NULL OR (ai_reason IS NOT NULL AND btrim(ai_reason) <> '')",
            name="ai_score_has_reason",
        ),
        CheckConstraint(
            "hr_score IS NULL OR (hr_reason IS NOT NULL AND btrim(hr_reason) <> '' AND hr_by IS NOT NULL AND hr_at IS NOT NULL)",
            name="hr_override_complete",
        ),
        CheckConstraint("ai_score IS NOT NULL OR hr_score IS NOT NULL", name="has_a_score"),
    )

    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id"), primary_key=True)
    ai_score: Mapped[int | None] = mapped_column(SmallInteger)
    ai_reason: Mapped[str | None] = mapped_column(Text)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    scored_at: Mapped[datetime | None]
    hr_score: Mapped[int | None] = mapped_column(SmallInteger)
    hr_reason: Mapped[str | None] = mapped_column(Text)
    hr_by: Mapped[str | None] = mapped_column(String(100))
    hr_at: Mapped[datetime | None]

    answer: Mapped[Answer] = relationship(back_populates="score")
