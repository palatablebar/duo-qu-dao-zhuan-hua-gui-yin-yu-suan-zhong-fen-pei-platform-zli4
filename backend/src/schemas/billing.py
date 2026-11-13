from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BillRowIn(BaseModel):
    channel_code: str = Field(min_length=2, max_length=40)
    kind: Literal["spend", "refund"]
    amount: float = Field(gt=0, le=50_000_000)
    memo: str | None = Field(default=None, max_length=200)


class BillBatchIn(BaseModel):
    batch_no: str = Field(min_length=4, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rows: list[BillRowIn] = Field(min_length=1, max_length=200)


class AdjustmentIn(BaseModel):
    channel_id: int = Field(ge=1)
    delta: float = Field(ge=-50_000_000, le=50_000_000)
    reason: str = Field(min_length=2, max_length=200)
    request_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
