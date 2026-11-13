"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.attribution_runs import router as attribution_runs_router
from src.routes.attributions import router as attributions_router
from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.channels import router as channels_router
from src.routes.conversions import router as conversions_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.overview import router as overview_router
from src.routes.touchpoints import router as touchpoints_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(channels_router)
api_router.include_router(touchpoints_router)
api_router.include_router(conversions_router)
api_router.include_router(attribution_runs_router)
api_router.include_router(attributions_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
