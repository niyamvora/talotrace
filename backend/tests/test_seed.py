from collections import Counter

from sqlalchemy import func, select

from app.config import settings
from app.models import Answer, Candidate, ScoringJob
from app.seed import seed


def test_seed_loads_the_pack_once(db, tmp_path):
    seed(db, settings.data_dir, tmp_path)
    seed(db, settings.data_dir, tmp_path)  # a re-run must not duplicate anything

    answers = {a.idempotency_key: a for a in db.scalars(select(Answer))}
    assert len(answers) == 35
    assert Counter(db.scalars(select(ScoringJob.status))) == {"queued": 28, "needs_person": 6}
    assert db.scalar(select(func.count()).select_from(Candidate)) == 18 + 5  # pack + one demo per role

    assert answers["A023"].is_current
    assert not answers["A022"].is_current and answers["A022"].job is None
    assert answers["A007"].job.needs_person_reason == "empty answer"
    assert answers["A031"].job.needs_person_reason == "audio received, not transcribed"
    assert (tmp_path / "A031.m4a").exists()
