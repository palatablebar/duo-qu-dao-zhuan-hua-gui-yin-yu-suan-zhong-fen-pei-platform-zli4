from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChannelIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=80)
    type: Literal["search", "feed", "content", "community", "live"]
    monthly_cost: float = Field(ge=0, le=50_000_000)
    budget: float = Field(ge=0, le=50_000_000)
    owner: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class ChannelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    type: Literal["search", "feed", "content", "community", "live"] | None = None
    monthly_cost: float | None = Field(default=None, ge=0, le=50_000_000)
    budget: float | None = Field(default=None, ge=0, le=50_000_000)
    owner: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
