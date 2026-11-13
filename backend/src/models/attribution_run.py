"""归因运行：一次马尔可夫 + Shapley 计算的完整快照。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class AttributionRun(Base):
    __tablename__ = "attribution_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    period: Mapped[str] = mapped_column(String(10), index=True)
    model: Mapped[str] = mapped_column(String(24), default="markov")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    operator_email: Mapped[str] = mapped_column(String(160), default="system")
    users_count: Mapped[int] = mapped_column(Integer, default=0)
    touchpoints_count: Mapped[int] = mapped_column(Integer, default=0)
    conversions_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
