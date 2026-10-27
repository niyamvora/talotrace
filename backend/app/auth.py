"""MOCK HR sign-in. "Continue with Google / Facebook" sends only an email, and we trust it:
no OAuth, no password. The API signs that identity into an httpOnly cookie and checks the
cookie on every /api/hr route (see require_hr). A real version would verify the provider's ID token.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from app.config import settings

COOKIE = "talotrace_hr"
MAX_AGE = 8 * 3600

router = APIRouter(prefix="/api/hr", tags=["hr sign-in (mock)"])


class HrUser(BaseModel):
    provider: Literal["google", "facebook"]
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sign(payload: str) -> str:
    return hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def require_hr(talotrace_hr: Annotated[str | None, Cookie()] = None) -> HrUser:
    """The one gate for every HR route. Cookie format: base64(json identity + expiry).hmac"""
    payload, _, signature = (talotrace_hr or "").rpartition(".")
    if not payload or not hmac.compare_digest(signature, _sign(payload)):
        raise HTTPException(401, "Sign in required")
    data = json.loads(base64.urlsafe_b64decode(payload))  # trusted from here: we signed it
    if data["exp"] < time.time():
        raise HTTPException(401, "Session expired, sign in again")
    return HrUser(provider=data["provider"], email=data["email"])


@router.post("/login")
def login(user: HrUser, response: Response) -> HrUser:
    payload = base64.urlsafe_b64encode(json.dumps(user.model_dump() | {"exp": time.time() + MAX_AGE}).encode()).decode()
    response.set_cookie(
        COOKIE, f"{payload}.{_sign(payload)}", max_age=MAX_AGE, httponly=True, samesite="lax", secure=settings.cookie_secure
    )
    return user


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE, httponly=True, samesite="lax", secure=settings.cookie_secure)
