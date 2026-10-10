from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from questline.api.dependencies import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, bool]:
    return {"ok": True}


@router.get("/health/ready")
async def ready(session: SessionDep) -> dict[str, bool]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"ok": True}
