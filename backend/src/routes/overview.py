from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.enums import Role
from src.middlewares.rbac import READ_ROLES, require_roles
from src.services import overview_service

router = APIRouter(tags=["overview"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return overview_service.overview(db, hide_costs=principal["role"] == Role.VIEWER.value)
