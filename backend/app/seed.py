"""`python -m app.seed`: loads the data pack. Safe to re-run: existing rows are kept, never duplicated.

- typed answer             -> job queued
- empty typed answer       -> job needs_person "empty answer"                    (A007)
- audio-only answer        -> .m4a copied to uploads/, job needs_person          (A031-A035)
- same candidate+question  -> the newest counts; older ones superseded, no job   (A022 -> A023)
- one demo candidate per role with no answers, for trying the candidate flow live
"""

import csv
import json
import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Answer, Candidate, Question, Role, ScoringJob, initial_job


def parse_questions(md: str) -> tuple[list[str], list[tuple[str, str, str]]]:
    """questions.md -> (role names, [(question id, text, 1-4 rubric)])."""
    roles = re.search(r"^Open roles: (.+)\.$", md, re.M).group(1).split(", ")
    questions = [
        (qid, text.strip(), "\n".join(line.removeprefix("- ").replace("**", "") for line in body.split("\n") if line.strip()))
        for qid, text, body in re.findall(r"^## (Q\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    ]
    return roles, questions


def seed(db: Session, data_dir: Path, uploads_dir: Path) -> None:
    roles, questions = parse_questions((data_dir / "questions.md").read_text())
    for name in roles:
        if not db.scalar(select(Role).where(Role.name == name)):
            db.add(Role(name=name))
    for qid, text, rubric in questions:
        db.merge(Question(id=qid, text=text, rubric=rubric))
    db.flush()
    role_by_name = {r.name: r for r in db.scalars(select(Role))}

    people = {row["candidate_id"]: row for row in csv.DictReader((data_dir / "pipeline_log.csv").open())}
    pack = sorted(
        (json.loads(p.read_text()) for p in (data_dir / "answers").glob("*.json")), key=lambda a: a["submitted_at"]
    )

    # Existing candidates keep their token, so links printed by an earlier run keep working.
    new_candidates = {a["candidate_id"]: (people[a["candidate_id"]], a["role"]) for a in pack}
    for i, name in enumerate(roles, 1):
        new_candidates[f"DEMO{i}"] = ({"candidate_name": f"Demo candidate ({name})", "candidate_email": f"demo{i}@example.com"}, name)
    for cid, (person, role) in new_candidates.items():
        if not db.get(Candidate, cid):
            db.add(Candidate(
                id=cid,
                role=role_by_name[role],
                name=person["candidate_name"],
                email=person["candidate_email"],
                access_token=secrets.token_urlsafe(24),
            ))
    db.flush()

    latest = {(a["candidate_id"], a["question_id"]): a["answer_id"] for a in pack}  # sorted, so the newest wins
    existing = {tuple(row) for row in db.execute(select(Answer.candidate_id, Answer.idempotency_key))}
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for a in pack:
        audio = a.get("audio_file")
        if audio:
            shutil.copyfile(data_dir / "answers" / audio, uploads_dir / audio)
        if (a["candidate_id"], a["answer_id"]) in existing:
            continue
        answer = Answer(
            candidate_id=a["candidate_id"],
            question_id=a["question_id"],
            kind="audio" if audio else "text",
            text=a["transcript"] if audio else a["transcript"] or "",
            audio_path=audio,
            duration_seconds=a["duration_seconds"],
            idempotency_key=a["answer_id"],
            is_current=latest[(a["candidate_id"], a["question_id"])] == a["answer_id"],
            # ponytail: the pack's timestamps carry no timezone; read as UTC
            submitted_at=datetime.fromisoformat(a["submitted_at"]).replace(tzinfo=UTC),
        )
        if answer.is_current:  # a superseded answer is never scored
            answer.job = initial_job(answer)
        db.add(answer)
    db.flush()


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db, settings.data_dir, settings.uploads_dir)
        db.commit()

        print("Candidate links:")
        for c in db.scalars(select(Candidate).order_by(Candidate.role_id, Candidate.id)):
            print(f"  {c.id:<6} {c.role.name:<27} {c.name:<36} {settings.web_url}/i/{c.access_token}")
        answers = db.scalar(select(func.count()).select_from(Answer))
        jobs = dict(db.execute(select(ScoringJob.status, func.count()).group_by(ScoringJob.status)).all())
        superseded = db.scalars(select(Answer.idempotency_key).where(~Answer.is_current)).all()
        print(f"\n{answers} answers | jobs: {jobs} | superseded: {', '.join(superseded) or 'none'}")


if __name__ == "__main__":
    main()
