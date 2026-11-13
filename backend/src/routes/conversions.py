from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.rbac import READ_ROLES, require_roles
from src.services import touchpoint_service
from src.utils.pagination import page_params

router = APIRouter(prefix="/conversions", tags=["conversions"])


@router.get("")
def list_conversions(
    q: str | None = None,
    min_amount: float | None = None,
    limit: int = Query(30),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return touchpoint_service.list_conversions(
        db, q=q, min_amount=min_amount, limit=page.limit, offset=page.offset
    )
