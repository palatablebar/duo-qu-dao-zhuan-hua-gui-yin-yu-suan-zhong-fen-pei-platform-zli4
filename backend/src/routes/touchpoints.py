from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.rbac import READ_ROLES, require_roles
from src.services import touchpoint_service
from src.utils.pagination import page_params

router = APIRouter(prefix="/touchpoints", tags=["touchpoints"])


@router.get("")
def list_touchpoints(
    channel_id: int | None = None,
    user_id: str | None = None,
    campaign: str | None = None,
    limit: int = Query(30),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return touchpoint_service.list_touchpoints(
        db,
        channel_id=channel_id,
        user_id=user_id,
        campaign=campaign,
        limit=page.limit,
        offset=page.offset,
    )
