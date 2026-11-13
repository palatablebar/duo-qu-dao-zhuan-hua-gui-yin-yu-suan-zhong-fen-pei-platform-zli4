from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CHANNEL_WRITE_ROLES
from src.controllers import channel_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.channel import ChannelIn, ChannelPatch
from src.utils.pagination import page_params

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
def list_channels(
    q: str | None = None,
    type: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return channel_controller.list_channels(
        db, principal, q=q, type=type, enabled=enabled, limit=page.limit, offset=page.offset
    )


@router.get("/{channel_id}")
def get_channel(
    channel_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return channel_controller.get_channel(db, channel_id, principal)


@router.post("", status_code=201)
def create_channel(
    payload: ChannelIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANNEL_WRITE_ROLES)),
) -> dict:
    return channel_controller.create_channel(db, payload.model_dump(), principal, request)


@router.patch("/{channel_id}")
def update_channel(
    channel_id: int,
    payload: ChannelPatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANNEL_WRITE_ROLES)),
) -> dict:
    return channel_controller.update_channel(
        db, channel_id, payload.model_dump(exclude_unset=True), principal, request
    )
