from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  registers tables on Base.metadata
from app.db import Base, engine, get_db
from app.routes import candidate, hr


@asynccontextmanager
async def lifespan(_: FastAPI):
    # ponytail: create_all instead of Alembic; add migrations once the schema changes after the demo
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="TaloTrace API", lifespan=lifespan)
app.include_router(candidate.router)
app.include_router(hr.router)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, bool]:
    db.execute(text("SELECT 1"))
    return {"ok": True}
