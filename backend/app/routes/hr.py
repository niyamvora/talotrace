"""HR API. Every route sits behind require_hr (Step 5)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/hr", tags=["hr"])
