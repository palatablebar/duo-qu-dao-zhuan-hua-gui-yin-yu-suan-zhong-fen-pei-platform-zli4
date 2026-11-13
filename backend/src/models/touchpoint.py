"""用户触点：路径构建的原始明细（渠道 × 时间 × 活动）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Touchpoint(Base):
    __tablename__ = "touchpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    touched_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    campaign: Mapped[str] = mapped_column(String(60), default="")
    seed_key: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
