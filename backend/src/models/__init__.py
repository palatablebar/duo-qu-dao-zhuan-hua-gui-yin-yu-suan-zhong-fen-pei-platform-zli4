"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.channel import Channel  # noqa: E402
from src.models.touchpoint import Touchpoint  # noqa: E402
from src.models.conversion import Conversion  # noqa: E402
from src.models.attribution_run import AttributionRun  # noqa: E402
from src.models.attribution import Attribution  # noqa: E402

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "Channel",
    "Touchpoint",
    "Conversion",
    "AttributionRun",
    "Attribution",
]
