from app.config import settings

# Tests never touch the dev database. Must run before app.db creates the engine.
if settings.test_database_url == settings.database_url:
    raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL: tests drop and recreate every table")
settings.database_url = settings.test_database_url

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402,F401  registers tables on Base.metadata
from app.db import Base, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    # Fresh tables every run, so the test DB always matches models.py.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def db():
    # Each test runs inside a transaction that is rolled back, so tests never see each other's rows.
    with engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        trans.rollback()
