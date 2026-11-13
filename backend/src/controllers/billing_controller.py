"""账单控制器：领域审计 + 事务提交。批次失败也提交（failed 批次记录），再以 422 告知。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.enums import BillBatchStatus
from src.models.channel import Channel
from src.services import audit_service, billing_service
from src.utils.errors import AppError


def overview(db: Session) -> dict:
    return billing_service.channel_balances(db)


def post_batch(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    batch, created = billing_service.submit_batch(db, payload, principal["email"])
    if created:
        audit_service.record(
            db,
            actor_email=principal["email"],
            actor_role=principal["role"],
            action="billing.post_batch",
            entity="bill_batch",
            entity_id=batch.id,
            detail={
                "batch_no": batch.batch_no,
                "status": batch.status,
                "rows": batch.row_count,
                "net_total": batch.net_total,
            },
            ip=request.client.host if request.client else None,
        )
    db.commit()
    if batch.status == BillBatchStatus.FAILED.value:
        raise AppError(
            "BATCH_FAILED",
            422,
            {"batch_no": batch.batch_no, "error": batch.error},
            message=f"整批入账失败：{batch.error}",
        )
    return billing_service.batch_detail(db, batch.id)


def list_batches(db: Session, **filters) -> dict:
    return billing_service.list_batches(db, **filters)


def get_batch(db: Session, batch_id: int) -> dict:
    return billing_service.batch_detail(db, batch_id)


def list_entries(db: Session, **filters) -> dict:
    return billing_service.list_entries(db, **filters)


def reverse_entry(db: Session, entry_id: int, principal: dict, request: Request) -> dict:
    batch = billing_service.reverse_entry(db, entry_id, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="billing.reverse",
        entity="bill_entry",
        entity_id=entry_id,
        detail={"batch_no": batch.batch_no, "net_total": batch.net_total},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return billing_service.batch_detail(db, batch.id)


def create_adjustment(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    adjustment, created = billing_service.create_adjustment(db, payload, principal["email"])
    if created:
        audit_service.record(
            db,
            actor_email=principal["email"],
            actor_role=principal["role"],
            action="budget.adjust",
            entity="budget_adjustment",
            entity_id=adjustment.id,
            detail={
                "adjust_no": adjustment.adjust_no,
                "delta": adjustment.delta,
                "hold_amount": adjustment.hold_amount,
            },
            ip=request.client.host if request.client else None,
        )
    db.commit()
    return billing_service.serialize_adjustment(adjustment, db.get(Channel, adjustment.channel_id))


def decide_adjustment(db: Session, adjustment_id: int, approve: bool, principal: dict, request: Request) -> dict:
    adjustment = billing_service.decide_adjustment(db, adjustment_id, approve, principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="budget.approve" if approve else "budget.reject",
        entity="budget_adjustment",
        entity_id=adjustment.id,
        detail={"adjust_no": adjustment.adjust_no, "status": adjustment.status, "delta": adjustment.delta},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return billing_service.serialize_adjustment(adjustment, db.get(Channel, adjustment.channel_id))


def list_adjustments(db: Session, **filters) -> dict:
    return billing_service.list_adjustments(db, **filters)
