"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "增长管理员",
    Role.ANALYST.value: "归因分析师",
    Role.VIEWER.value: "渠道只读",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "维护渠道与预算、发起归因、导出报表、查看审计",
    Role.ANALYST.value: "发起归因运行、复核归因结果与预算建议",
    Role.VIEWER.value: "只读归因结果（成本明细已隐藏）",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "overview:read",
        "channel:read", "channel:write",
        "touchpoint:read", "conversion:read",
        "run:read", "run:create",
        "attribution:read", "attribution:review",
        "plan:read", "export:read", "audit:read",
    },
    Role.ANALYST.value: {
        "overview:read",
        "channel:read",
        "touchpoint:read", "conversion:read",
        "run:read", "run:create",
        "attribution:read", "attribution:review",
        "plan:read",
    },
    Role.VIEWER.value: {
        "overview:read", "channel:read", "run:read", "attribution:read", "plan:read",
    },
}

CHANNEL_WRITE_ROLES = (Role.ADMIN.value,)
RUN_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
REVIEW_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
EXPORT_ROLES = (Role.ADMIN.value,)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
