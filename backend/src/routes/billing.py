from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import BILLING_READ_ROLES, BILLING_WRITE_ROLES
from src.controllers import billing_controller
from src.middlewares.rbac import require_roles
from src.schemas.billing import AdjustmentIn, BillBatchIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_READ_ROLES)),
) -> dict:
    return billing_controller.overview(db)


@router.get("/batches")
def list_batches(
    status: str | None = None,
    period: str | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return billing_controller.list_batches(db, status=status, period=period, limit=page.limit, offset=page.offset)


@router.post("/batches", status_code=201)
def post_batch(
    payload: BillBatchIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_WRITE_ROLES)),
) -> dict:
    return billing_controller.post_batch(db, payload.model_dump(), principal, request)


@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_READ_ROLES)),
) -> dict:
    return billing_controller.get_batch(db, batch_id)


@router.get("/entries")
def list_entries(
    channel_id: int | None = None,
    kind: str | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return billing_controller.list_entries(db, channel_id=channel_id, kind=kind, limit=page.limit, offset=page.offset)


@router.post("/entries/{entry_id}/reverse", status_code=201)
def reverse_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_WRITE_ROLES)),
) -> dict:
    return billing_controller.reverse_entry(db, entry_id, principal, request)


@router.get("/adjustments")
def list_adjustments(
    status: str | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return billing_controller.list_adjustments(db, status=status, limit=page.limit, offset=page.offset)


@router.post("/adjustments", status_code=201)
def create_adjustment(
    payload: AdjustmentIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_WRITE_ROLES)),
) -> dict:
    return billing_controller.create_adjustment(db, payload.model_dump(), principal, request)


@router.post("/adjustments/{adjustment_id}/approve")
def approve_adjustment(
    adjustment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_WRITE_ROLES)),
) -> dict:
    return billing_controller.decide_adjustment(db, adjustment_id, True, principal, request)


@router.post("/adjustments/{adjustment_id}/reject")
def reject_adjustment(
    adjustment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*BILLING_WRITE_ROLES)),
) -> dict:
    return billing_controller.decide_adjustment(db, adjustment_id, False, principal, request)
