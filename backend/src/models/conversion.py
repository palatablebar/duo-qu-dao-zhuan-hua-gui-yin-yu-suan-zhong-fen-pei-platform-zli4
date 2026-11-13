"""转化订单：金额与订单号，归属到用户维度。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    converted_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    seed_key: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
