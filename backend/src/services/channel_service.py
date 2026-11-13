"""渠道服务：CRUD + 视图序列化（viewer 隐藏成本明细）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import CHANNEL_TYPE_LABELS
from src.models.channel import Channel
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(channel: Channel, hide_costs: bool = False) -> dict:
    payload = {
        "id": channel.id,
        "code": channel.code,
        "name": channel.name,
        "type": channel.type,
        "type_label": CHANNEL_TYPE_LABELS.get(channel.type, channel.type),
        "owner": channel.owner,
        "note": channel.note,
        "enabled": channel.enabled,
        "created_at": iso_utc(channel.created_at),
        "updated_at": iso_utc(channel.updated_at),
        "monthly_cost": None if hide_costs else round(float(channel.monthly_cost), 2),
        "budget": None if hide_costs else round(float(channel.budget), 2),
        "costs_hidden": hide_costs,
    }
    return payload


def list_channels(
    db: Session,
    q: str | None = None,
    type: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    hide_costs: bool = False,
) -> dict:
    stmt = select(Channel)
    count_stmt = select(func.count()).select_from(Channel)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Channel.name.ilike(like) | Channel.code.ilike(like))
        count_stmt = count_stmt.where(Channel.name.ilike(like) | Channel.code.ilike(like))
    if type:
        stmt = stmt.where(Channel.type == type)
        count_stmt = count_stmt.where(Channel.type == type)
    if enabled is not None:
        stmt = stmt.where(Channel.enabled == enabled)
        count_stmt = count_stmt.where(Channel.enabled == enabled)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Channel.id).limit(limit).offset(offset)).all()
    return {
        "items": [serialize(row, hide_costs) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_channel(db: Session, channel_id: int) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise not_found("channel", channel_id)
    return channel


def create_channel(db: Session, payload: dict) -> Channel:
    exists = db.scalar(select(Channel).where(Channel.code == payload["code"]))
    if exists is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    channel = Channel(
        code=payload["code"],
        name=payload["name"],
        type=payload["type"],
        monthly_cost=float(payload["monthly_cost"]),
        budget=float(payload["budget"]),
        owner=payload.get("owner") or "清野日化 · 增长组",
        note=payload.get("note"),
        enabled=True,
    )
    db.add(channel)
    db.flush()
    return channel


def update_channel(db: Session, channel: Channel, payload: dict) -> Channel:
    for field in ("name", "type", "monthly_cost", "budget", "owner", "note", "enabled"):
        if field in payload and payload[field] is not None:
            setattr(channel, field, payload[field])
    db.flush()
    return channel


def total_budget(db: Session) -> float:
    return round(float(db.scalar(select(func.coalesce(func.sum(Channel.budget), 0.0))) or 0.0), 2)
