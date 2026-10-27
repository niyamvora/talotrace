"""HR API. require_hr sits on the router, so every route here (and every route added later) needs sign-in."""

from fastapi import APIRouter, Depends

from app.auth import HrUser, require_hr

router = APIRouter(prefix="/api/hr", tags=["hr"], dependencies=[Depends(require_hr)])


@router.get("/me")
def me(user: HrUser = Depends(require_hr)) -> HrUser:
    return user
