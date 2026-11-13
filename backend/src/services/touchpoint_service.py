"""触点与转化明细查询（归因链路的证据层）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.channel import Channel
from src.models.conversion import Conversion
from src.models.touchpoint import Touchpoint
from src.utils.timeutil import iso_utc


def serialize_touchpoint(row: Touchpoint, channel: Channel | None) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "channel_id": row.channel_id,
        "channel_code": channel.code if channel else None,
        "channel_name": channel.name if channel else None,
        "touched_at": iso_utc(row.touched_at),
        "cost": round(float(row.cost), 2),
        "campaign": row.campaign,
    }


def list_touchpoints(
    db: Session,
    *,
    channel_id: int | None = None,
    user_id: str | None = None,
    campaign: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict:
    stmt = select(Touchpoint)
    count_stmt = select(func.count()).select_from(Touchpoint)
    if channel_id:
        stmt = stmt.where(Touchpoint.channel_id == channel_id)
        count_stmt = count_stmt.where(Touchpoint.channel_id == channel_id)
    if user_id:
        like = f"%{user_id.strip()}%"
        stmt = stmt.where(Touchpoint.user_id.ilike(like))
        count_stmt = count_stmt.where(Touchpoint.user_id.ilike(like))
    if campaign:
        like = f"%{campaign.strip()}%"
        stmt = stmt.where(Touchpoint.campaign.ilike(like))
        count_stmt = count_stmt.where(Touchpoint.campaign.ilike(like))
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Touchpoint.touched_at.desc()).limit(limit).offset(offset)).all()
    channels = {row.id: row for row in db.scalars(select(Channel)).all()}
    return {
        "items": [serialize_touchpoint(row, channels.get(row.channel_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def serialize_conversion(row: Conversion) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "amount": round(float(row.amount), 2),
        "converted_at": iso_utc(row.converted_at),
        "order_no": row.order_no,
    }


def list_conversions(
    db: Session,
    *,
    q: str | None = None,
    min_amount: float | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict:
    stmt = select(Conversion)
    count_stmt = select(func.count()).select_from(Conversion)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Conversion.order_no.ilike(like) | Conversion.user_id.ilike(like))
        count_stmt = count_stmt.where(Conversion.order_no.ilike(like) | Conversion.user_id.ilike(like))
    if min_amount is not None:
        stmt = stmt.where(Conversion.amount >= min_amount)
        count_stmt = count_stmt.where(Conversion.amount >= min_amount)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Conversion.converted_at.desc()).limit(limit).offset(offset)).all()
    amount_total = db.scalar(select(func.coalesce(func.sum(Conversion.amount), 0.0))) or 0.0
    return {
        "items": [serialize_conversion(row) for row in rows],
        "total": total,
        "amount_total": round(float(amount_total), 2),
        "limit": limit,
        "offset": offset,
    }
