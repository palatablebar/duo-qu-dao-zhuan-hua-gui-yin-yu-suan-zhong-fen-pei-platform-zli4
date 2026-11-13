"""账单与预算占用服务。

不变量：
1. 批次整批成功或整批失败：全部行先校验，再在同一事务写入；任何一行出错，
   只落一条 failed 批次记录（含失败原因），分录零写入。
2. 台账只追加：bill_entries 永不 UPDATE/DELETE；纠错用 reversal 分录冲正，
   reverses_id 唯一约束保证一条记录只能被冲正一次。
3. 预算调整先占用再批准：占用用一条原子 UPDATE 完成「校验 + 扣减可用余额」，
   两名经理同时提交时数据库行锁串行化，第二名必然收到 409，不会占用同一笔余额。
4. 可用余额 = 月度预算 − 净消耗 − 在途占用；页面与导出共用 channel_balances()。
"""
from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.constants.enums import (
    ADJUST_STATUS_LABELS,
    BILL_BATCH_KIND_LABELS,
    BILL_BATCH_STATUS_LABELS,
    BILL_KIND_LABELS,
    CHANNEL_TYPE_LABELS,
    AdjustStatus,
    BillBatchKind,
    BillBatchStatus,
    BillEntryKind,
)
from src.models.billing import BillBatch, BillEntry, BudgetAdjustment
from src.models.channel import Channel
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, utcnow


# ---------- 序列化 ----------

def serialize_entry(entry: BillEntry, channel: Channel | None = None, reversed_by: int | None = None) -> dict:
    return {
        "id": entry.id,
        "entry_no": entry.entry_no,
        "batch_id": entry.batch_id,
        "channel_id": entry.channel_id,
        "channel_code": channel.code if channel else None,
        "channel_name": channel.name if channel else None,
        "kind": entry.kind,
        "kind_label": BILL_KIND_LABELS.get(entry.kind, entry.kind),
        "amount": round(float(entry.amount), 2),
        "memo": entry.memo,
        "row_no": entry.row_no,
        "reverses_id": entry.reverses_id,
        "reversed_by": reversed_by,
        "created_at": iso_utc(entry.created_at),
    }


def serialize_batch(batch: BillBatch, entries: list[dict] | None = None) -> dict:
    payload = {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "period": batch.period,
        "kind": batch.kind,
        "kind_label": BILL_BATCH_KIND_LABELS.get(batch.kind, batch.kind),
        "status": batch.status,
        "status_label": BILL_BATCH_STATUS_LABELS.get(batch.status, batch.status),
        "row_count": batch.row_count,
        "spend_total": round(float(batch.spend_total), 2),
        "refund_total": round(float(batch.refund_total), 2),
        "net_total": round(float(batch.net_total), 2),
        "error": batch.error,
        "created_by": batch.created_by,
        "created_at": iso_utc(batch.created_at),
    }
    if entries is not None:
        payload["entries"] = entries
    return payload


def serialize_adjustment(adjustment: BudgetAdjustment, channel: Channel | None = None) -> dict:
    return {
        "id": adjustment.id,
        "adjust_no": adjustment.adjust_no,
        "channel_id": adjustment.channel_id,
        "channel_code": channel.code if channel else None,
        "channel_name": channel.name if channel else None,
        "delta": round(float(adjustment.delta), 2),
        "hold_amount": round(float(adjustment.hold_amount), 2),
        "reason": adjustment.reason,
        "status": adjustment.status,
        "status_label": ADJUST_STATUS_LABELS.get(adjustment.status, adjustment.status),
        "request_key": adjustment.request_key,
        "created_by": adjustment.created_by,
        "created_at": iso_utc(adjustment.created_at),
        "decided_by": adjustment.decided_by,
        "decided_at": iso_utc(adjustment.decided_at),
    }


# ---------- 余额（页面与导出唯一口径） ----------

def channel_balances(db: Session) -> dict:
    channels = db.scalars(select(Channel).order_by(Channel.id)).all()
    net_rows = db.execute(
        select(BillEntry.channel_id, func.coalesce(func.sum(BillEntry.amount), 0.0)).group_by(BillEntry.channel_id)
    ).all()
    net_by_channel = {channel_id: float(net) for channel_id, net in net_rows}
    items = []
    for channel in channels:
        budget = round(float(channel.budget), 2)
        net_spend = round(net_by_channel.get(channel.id, 0.0), 2)
        held = round(float(channel.held_amount or 0.0), 2)
        items.append(
            {
                "channel_id": channel.id,
                "code": channel.code,
                "name": channel.name,
                "type": channel.type,
                "type_label": CHANNEL_TYPE_LABELS.get(channel.type, channel.type),
                "budget": budget,
                "net_spend": net_spend,
                "held": held,
                "available": round(budget - net_spend - held, 2),
                "enabled": channel.enabled,
            }
        )
    totals = {key: round(sum(item[key] for item in items), 2) for key in ("budget", "net_spend", "held", "available")}
    return {"items": items, "totals": totals}


# ---------- 批次入账（整批原子 + 幂等） ----------

def _fingerprint(period: str, rows: list[dict]) -> str:
    canonical = json.dumps(
        {
            "period": period,
            "rows": [
                {
                    "channel_code": row["channel_code"],
                    "kind": row["kind"],
                    "amount": round(float(row["amount"]), 2),
                    "memo": row.get("memo") or "",
                }
                for row in rows
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_rows(db: Session, rows: list[dict]) -> tuple[list[str], dict[str, Channel]]:
    channels = {channel.code: channel for channel in db.scalars(select(Channel)).all()}
    errors: list[str] = []
    for idx, row in enumerate(rows, start=1):
        channel = channels.get(row["channel_code"])
        if channel is None:
            errors.append(f"第{idx}行：渠道 {row['channel_code']} 不存在")
        elif not channel.enabled:
            errors.append(f"第{idx}行：渠道「{channel.name}」已停用")
        if float(row["amount"]) <= 0:
            errors.append(f"第{idx}行：金额必须大于 0")
    return errors, channels


def submit_batch(db: Session, payload: dict, operator_email: str) -> tuple[BillBatch, bool]:
    """返回 (批次, 是否新建)。同 batch_no + 同内容 → 返回原批次（幂等重放）。"""
    batch_no = payload["batch_no"]
    rows = payload["rows"]
    fingerprint = _fingerprint(payload["period"], rows)
    existing = db.scalar(select(BillBatch).where(BillBatch.batch_no == batch_no))
    if existing is not None:
        if existing.payload_hash == fingerprint:
            return existing, False
        raise AppError(
            "CONFLICT",
            409,
            {"batch_no": batch_no, "status": existing.status},
            message="批次号已存在且内容不一致，请更换批次号",
        )
    errors, channels = _validate_rows(db, rows)
    failed = bool(errors)
    spend_total = round(sum(float(row["amount"]) for row in rows if row["kind"] == BillEntryKind.SPEND.value), 2)
    refund_total = round(sum(float(row["amount"]) for row in rows if row["kind"] == BillEntryKind.REFUND.value), 2)
    batch = BillBatch(
        batch_no=batch_no,
        period=payload["period"],
        kind=BillBatchKind.ENTRY.value,
        status=BillBatchStatus.FAILED.value if failed else BillBatchStatus.POSTED.value,
        row_count=len(rows),
        spend_total=0.0 if failed else spend_total,
        refund_total=0.0 if failed else refund_total,
        net_total=0.0 if failed else round(spend_total - refund_total, 2),
        error="；".join(errors) if failed else None,
        payload_hash=fingerprint,
        created_by=operator_email,
    )
    db.add(batch)
    try:
        db.flush()
        if not failed:
            for idx, row in enumerate(rows, start=1):
                sign = 1.0 if row["kind"] == BillEntryKind.SPEND.value else -1.0
                db.add(
                    BillEntry(
                        entry_no=f"{batch_no}-{idx:03d}",
                        batch_id=batch.id,
                        channel_id=channels[row["channel_code"]].id,
                        kind=row["kind"],
                        amount=round(sign * float(row["amount"]), 2),
                        memo=row.get("memo"),
                        row_no=idx,
                    )
                )
            db.flush()
    except IntegrityError:
        # 并发下同号批次只会有一个落库；回滚后按幂等重放处理
        db.rollback()
        existing = db.scalar(select(BillBatch).where(BillBatch.batch_no == batch_no))
        if existing is not None and existing.payload_hash == fingerprint:
            return existing, False
        raise AppError("CONFLICT", 409, {"batch_no": batch_no}, message="批次号冲突，请更换批次号")
    return batch, True


def get_batch(db: Session, batch_id: int) -> BillBatch:
    batch = db.get(BillBatch, batch_id)
    if batch is None:
        raise not_found("bill_batch", batch_id)
    return batch


def _reversed_map(db: Session, entry_ids: list[int]) -> dict[int, int]:
    if not entry_ids:
        return {}
    rows = db.execute(
        select(BillEntry.reverses_id, BillEntry.id).where(BillEntry.reverses_id.in_(entry_ids))
    ).all()
    return {reverses_id: reversal_id for reverses_id, reversal_id in rows}


def batch_detail(db: Session, batch_id: int) -> dict:
    batch = get_batch(db, batch_id)
    entries = db.scalars(
        select(BillEntry).where(BillEntry.batch_id == batch.id).order_by(BillEntry.row_no)
    ).all()
    channels = {channel.id: channel for channel in db.scalars(select(Channel)).all()}
    reversed_map = _reversed_map(db, [entry.id for entry in entries])
    return serialize_batch(
        batch,
        entries=[
            serialize_entry(entry, channels.get(entry.channel_id), reversed_map.get(entry.id)) for entry in entries
        ],
    )


def list_batches(db: Session, status: str | None = None, period: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    stmt = select(BillBatch)
    count_stmt = select(func.count()).select_from(BillBatch)
    if status:
        stmt = stmt.where(BillBatch.status == status)
        count_stmt = count_stmt.where(BillBatch.status == status)
    if period:
        stmt = stmt.where(BillBatch.period == period)
        count_stmt = count_stmt.where(BillBatch.period == period)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(BillBatch.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [serialize_batch(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def list_entries(
    db: Session, channel_id: int | None = None, kind: str | None = None, limit: int = 50, offset: int = 0
) -> dict:
    stmt = select(BillEntry)
    count_stmt = select(func.count()).select_from(BillEntry)
    if channel_id:
        stmt = stmt.where(BillEntry.channel_id == channel_id)
        count_stmt = count_stmt.where(BillEntry.channel_id == channel_id)
    if kind:
        stmt = stmt.where(BillEntry.kind == kind)
        count_stmt = count_stmt.where(BillEntry.kind == kind)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(BillEntry.id.desc()).limit(limit).offset(offset)).all()
    channels = {channel.id: channel for channel in db.scalars(select(Channel)).all()}
    reversed_map = _reversed_map(db, [entry.id for entry in rows])
    return {
        "items": [
            serialize_entry(entry, channels.get(entry.channel_id), reversed_map.get(entry.id)) for entry in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------- 冲正（只追加，不改历史） ----------

def reverse_entry(db: Session, entry_id: int, operator_email: str) -> BillBatch:
    entry = db.get(BillEntry, entry_id)
    if entry is None:
        raise not_found("bill_entry", entry_id)
    if entry.kind == BillEntryKind.REVERSAL.value:
        raise AppError("VALIDATION", 422, {"entry_no": entry.entry_no}, message="冲正记录不能再次冲正")
    existing = db.scalar(select(BillEntry).where(BillEntry.reverses_id == entry.id))
    if existing is not None:
        raise AppError("CONFLICT", 409, {"entry_no": entry.entry_no}, message="该记录已被冲正")
    source_batch = db.get(BillBatch, entry.batch_id)
    reversal_no = f"RV-{entry.entry_no}"
    amount = round(-float(entry.amount), 2)
    batch = BillBatch(
        batch_no=reversal_no,
        period=source_batch.period if source_batch else "",
        kind=BillBatchKind.REVERSAL.value,
        status=BillBatchStatus.POSTED.value,
        row_count=1,
        spend_total=amount if amount > 0 else 0.0,
        refund_total=-amount if amount < 0 else 0.0,
        net_total=amount,
        error=None,
        payload_hash=f"reverse:{entry.entry_no}",
        created_by=operator_email,
    )
    db.add(batch)
    try:
        db.flush()
        db.add(
            BillEntry(
                entry_no=f"{reversal_no}-001",
                batch_id=batch.id,
                channel_id=entry.channel_id,
                kind=BillEntryKind.REVERSAL.value,
                amount=amount,
                reverses_id=entry.id,
                memo=f"冲正 {entry.entry_no}",
                row_no=1,
            )
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("CONFLICT", 409, {"entry_no": entry.entry_no}, message="该记录已被冲正")
    return batch


# ---------- 预算调整（先占用再批准） ----------

def _net_spend_subquery():
    return (
        select(func.coalesce(func.sum(BillEntry.amount), 0.0))
        .where(BillEntry.channel_id == Channel.id)
        .correlate(Channel)
        .scalar_subquery()
    )


def create_adjustment(db: Session, payload: dict, operator_email: str) -> tuple[BudgetAdjustment, bool]:
    """返回 (调整单, 是否新建)。request_key 相同 → 返回原单（幂等重放）。

    占用用一条原子 UPDATE 完成：只有「预算 − 在途占用 − 净消耗 >= 占用额」才扣减，
    并发提交由数据库行锁串行化，不会占用同一笔余额。
    """
    existing = db.scalar(select(BudgetAdjustment).where(BudgetAdjustment.request_key == payload["request_key"]))
    if existing is not None:
        return existing, False
    channel = db.get(Channel, payload["channel_id"])
    if channel is None:
        raise not_found("channel", payload["channel_id"])
    delta = round(float(payload["delta"]), 2)
    if delta == 0:
        raise AppError("VALIDATION", 422, {"delta": delta}, message="调整金额不能为 0")
    hold = round(max(0.0, -delta), 2)
    if hold > 0:
        result = db.execute(
            update(Channel)
            .where(Channel.id == channel.id)
            .where(Channel.budget - Channel.held_amount - _net_spend_subquery() >= hold)
            .values(held_amount=Channel.held_amount + hold)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            net_spend = float(
                db.scalar(select(func.coalesce(func.sum(BillEntry.amount), 0.0)).where(BillEntry.channel_id == channel.id))
                or 0.0
            )
            available = round(float(channel.budget) - float(channel.held_amount or 0.0) - net_spend, 2)
            raise AppError(
                "INSUFFICIENT_BALANCE",
                409,
                {"channel": channel.code, "available": available, "requested": hold},
                message=f"可用余额不足：当前可用 {available:,.2f} 元，可能有其他占用在途",
            )
        db.refresh(channel)
    adjustment = BudgetAdjustment(
        adjust_no=f"ADJ-{uuid.uuid4().hex[:10].upper()}",
        channel_id=channel.id,
        delta=delta,
        hold_amount=hold,
        reason=payload["reason"],
        status=AdjustStatus.HELD.value,
        request_key=payload["request_key"],
        created_by=operator_email,
    )
    db.add(adjustment)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(BudgetAdjustment).where(BudgetAdjustment.request_key == payload["request_key"]))
        if existing is not None:
            return existing, False
        raise
    return adjustment, True


def decide_adjustment(db: Session, adjustment_id: int, approve: bool, decided_by: str) -> BudgetAdjustment:
    """held → approved/rejected 状态 CAS；批准时预算与占用在同一事务回写。"""
    adjustment = db.get(BudgetAdjustment, adjustment_id)
    if adjustment is None:
        raise not_found("budget_adjustment", adjustment_id)
    new_status = AdjustStatus.APPROVED.value if approve else AdjustStatus.REJECTED.value
    result = db.execute(
        update(BudgetAdjustment)
        .where(BudgetAdjustment.id == adjustment.id)
        .where(BudgetAdjustment.status == AdjustStatus.HELD.value)
        .values(status=new_status, decided_by=decided_by, decided_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise AppError(
            "CONFLICT",
            409,
            {"adjust_no": adjustment.adjust_no, "status": adjustment.status},
            message="该调整已被处理，请刷新查看",
        )
    values: dict = {"held_amount": Channel.held_amount - adjustment.hold_amount}
    if approve:
        values["budget"] = Channel.budget + adjustment.delta
    db.execute(
        update(Channel)
        .where(Channel.id == adjustment.channel_id)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    db.flush()
    db.refresh(adjustment)
    return adjustment


def list_adjustments(db: Session, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    stmt = select(BudgetAdjustment)
    count_stmt = select(func.count()).select_from(BudgetAdjustment)
    if status:
        stmt = stmt.where(BudgetAdjustment.status == status)
        count_stmt = count_stmt.where(BudgetAdjustment.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(BudgetAdjustment.id.desc()).limit(limit).offset(offset)).all()
    channels = {channel.id: channel for channel in db.scalars(select(Channel)).all()}
    return {
        "items": [serialize_adjustment(row, channels.get(row.channel_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
