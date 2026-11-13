"""账单批次 / 台账分录 / 预算调整：整批原子入账、只追加冲正、先占用再批准。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class BillBatch(Base):
    """账单批次：batch_no 是幂等键；status 只有 posted/failed，不存在部分写入。"""

    __tablename__ = "bill_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    period: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="entry")
    status: Mapped[str] = mapped_column(String(16), default="posted", index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    spend_total: Mapped[float] = mapped_column(Float, default=0.0)
    refund_total: Mapped[float] = mapped_column(Float, default=0.0)
    net_total: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BillEntry(Base):
    """台账分录：只追加，不更新不删除；纠错用 reversal 分录冲正（reverses_id 唯一）。"""

    __tablename__ = "bill_entries"
    __table_args__ = (UniqueConstraint("batch_id", "row_no", name="uq_bill_entries_batch_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_no: Mapped[str] = mapped_column(String(64), unique=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("bill_batches.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Float, default=0.0)  # 消耗>0 退款<0 冲正=−原分录
    reverses_id: Mapped[int | None] = mapped_column(ForeignKey("bill_entries.id"), unique=True, nullable=True)
    memo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    row_no: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BudgetAdjustment(Base):
    """预算调整：先占用（held）再批准（approved）/驳回（rejected）；request_key 幂等。"""

    __tablename__ = "budget_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    adjust_no: Mapped[str] = mapped_column(String(48), unique=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    delta: Mapped[float] = mapped_column(Float, default=0.0)
    hold_amount: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="held", index=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
