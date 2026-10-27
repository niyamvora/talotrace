from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # Predictable constraint names (e.g. uq_answers_candidate_id_idempotency_key) so the API
    # can tell which rule an IntegrityError broke.
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
    )
    type_annotation_map = {datetime: DateTime(timezone=True)}


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
