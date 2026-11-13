from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RunIn(BaseModel):
    period: str = Field(default="2026-10", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    model: Literal["markov", "last_click", "shapley"] = "markov"
    trigger: Literal["manual", "schedule"] = "manual"


class ReviewIn(BaseModel):
    status: Literal["pending", "confirmed", "dismissed"]
    note: str | None = Field(default=None, max_length=500)
