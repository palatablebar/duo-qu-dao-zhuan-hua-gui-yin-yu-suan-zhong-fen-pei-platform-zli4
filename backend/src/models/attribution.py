"""单个渠道在某次运行中的归因结果与预算建议。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Attribution(Base):
    __tablename__ = "attributions"
    __table_args__ = (UniqueConstraint("run_id", "channel_id", name="uq_attributions_run_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("attribution_runs.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    credit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    share: Mapped[float] = mapped_column(Float, default=0.0)
    markov_share: Mapped[float] = mapped_column(Float, default=0.0)
    last_click_share: Mapped[float] = mapped_column(Float, default=0.0)
    shapley_share: Mapped[float] = mapped_column(Float, default=0.0)
    removal_effect: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_budget: Mapped[float] = mapped_column(Float, default=0.0)
    delta_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
