from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import REVIEW_ROLES
from src.controllers import attribution_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.attribution import ReviewIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/attributions", tags=["attributions"])


@router.get("")
def list_attributions(
    run_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return attribution_controller.list_attributions(
        db, principal, run_id=run_id, status=status, limit=page.limit, offset=page.offset
    )


@router.patch("/{attribution_id}/review")
def review(
    attribution_id: int,
    payload: ReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*REVIEW_ROLES)),
) -> dict:
    return attribution_controller.review(db, attribution_id, payload.model_dump(), principal, request)
