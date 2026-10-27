"""Candidate API. Response schemas here never carry a score, reason or status (Step 4)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/interview", tags=["candidate"])
