"""归因控制器：运行、结果、预算方案、复核。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.enums import Role
from src.services import attribution_service, audit_service


def _hide(principal: dict) -> bool:
    return principal["role"] == Role.VIEWER.value


def create_run(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    run = attribution_service.create_and_execute(
        db,
        period=payload["period"],
        model=payload["model"],
        trigger=payload.get("trigger") or "manual",
        operator_email=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.create",
        entity="attribution_run",
        entity_id=run.id,
        detail={"run_no": run.run_no, "period": run.period, "status": run.status},
        ip=request.client.host if request.client else None,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.complete",
        entity="attribution_run",
        entity_id=run.id,
        detail={"status": run.status, "attributions": run.metrics.get("conversions") if run.metrics else None},
        layer="domain",
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return attribution_service.serialize_run(run)


def list_runs(db: Session, **filters) -> dict:
    return attribution_service.list_runs(db, **filters)


def get_run(db: Session, run_id: int) -> dict:
    return attribution_service.serialize_run(attribution_service.get_run(db, run_id))


def list_attributions(db: Session, principal: dict, **filters) -> dict:
    return attribution_service.list_attributions(db, hide_costs=_hide(principal), **filters)


def plan(db: Session, run_id: int, principal: dict) -> dict:
    run = attribution_service.get_run(db, run_id)
    return attribution_service.plan_for_run(db, run, hide_costs=_hide(principal))


def review(db: Session, attribution_id: int, payload: dict, principal: dict, request: Request) -> dict:
    from src.models.attribution_run import AttributionRun
    from src.models.channel import Channel

    row = attribution_service.get_attribution(db, attribution_id)
    attribution_service.review(
        db, row, status=payload["status"], note=payload.get("note"), reviewer=principal["email"]
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="attribution.review",
        entity="attribution",
        entity_id=row.id,
        detail={"status": row.status, "share": round(row.share, 6)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    channel = db.get(Channel, row.channel_id)
    run_row = db.get(AttributionRun, row.run_id)
    return attribution_service.serialize_attribution(row, channel, run_row, hide_costs=_hide(principal))
