"""幂等 seed：3 账号 / 5 渠道 / 2,400 用户 / 8,600 触点 / 640 转化 / 1 次归因运行 / 5 条 Attribution。

自然键 upsert：
  users.email
  channels.code
  touchpoints.seed_key / conversions.seed_key（缺失才整批写入）
  attribution_runs.seed_key（存在则直接复用，不重算）
  audit_logs.seed_key

重复执行不新增、不覆盖用户改过的复核状态；SEED_SUMMARY 逐字一致。
"""
from __future__ import annotations

from sqlalchemy import func, select

from scripts.business_seed import BRAND, CHANNELS, PERIOD, build_dataset
from scripts.demo_config import DEMO_PASSWORD, DEMO_USERS, ORG, SEED_AUDIT, SEED_RUN_KEY
from src.config.database import session_scope
from src.models.attribution import Attribution
from src.models.attribution_run import AttributionRun
from src.models.audit import AuditLog
from src.models.channel import Channel
from src.models.conversion import Conversion
from src.models.touchpoint import Touchpoint
from src.models.user import User
from src.services import attribution_service
from src.utils.security import hash_password


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_channels(db) -> int:
    for spec in CHANNELS:
        channel = db.scalar(select(Channel).where(Channel.code == spec["code"]))
        if channel is None:
            db.add(
                Channel(
                    code=spec["code"],
                    name=spec["name"],
                    type=spec["type"],
                    monthly_cost=float(spec["monthly_cost"]),
                    budget=float(spec["budget"]),
                    owner=spec.get("owner") or ORG,
                    note=spec.get("note"),
                    enabled=True,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(Channel)) or 0


def ensure_events(db) -> tuple[int, int]:
    channels = {channel.code: channel.id for channel in db.scalars(select(Channel)).all()}
    dataset = build_dataset()

    touchpoint_total = db.scalar(select(func.count()).select_from(Touchpoint)) or 0
    if touchpoint_total == 0:
        rows = [
            {
                "user_id": row["user_id"],
                "channel_id": channels[row["channel_code"]],
                "touched_at": row["touched_at"].replace("T", " "),
                "cost": row["cost"],
                "campaign": row["campaign"],
                "seed_key": row["seed_key"],
            }
            for row in dataset["touchpoints"]
            if row["channel_code"] in channels
        ]
        db.execute(Touchpoint.__table__.insert(), rows)

    conversion_total = db.scalar(select(func.count()).select_from(Conversion)) or 0
    if conversion_total == 0:
        rows = [
            {
                "user_id": row["user_id"],
                "amount": row["amount"],
                "converted_at": row["converted_at"].replace("T", " "),
                "order_no": row["order_no"],
                "seed_key": row["seed_key"],
            }
            for row in dataset["conversions"]
        ]
        db.execute(Conversion.__table__.insert(), rows)
    db.flush()
    return (
        db.scalar(select(func.count()).select_from(Touchpoint)) or 0,
        db.scalar(select(func.count()).select_from(Conversion)) or 0,
    )


def ensure_run(db) -> int:
    existing = db.scalar(select(AttributionRun).where(AttributionRun.seed_key == SEED_RUN_KEY))
    if existing is None:
        attribution_service.create_and_execute(
            db,
            period=PERIOD,
            model="markov",
            trigger="seed",
            operator_email="analyst@mixcredit.io",
            seed_key=SEED_RUN_KEY,
        )
    db.flush()
    return db.scalar(select(func.count()).select_from(AttributionRun)) or 0


def ensure_audit(db) -> None:
    for seed_key, email, role, action, entity, detail in SEED_AUDIT:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    with session_scope() as db:
        users = ensure_users(db)
        sources = ensure_channels(db)
        db.flush()
        ensure_events(db)
        runs = ensure_run(db)
        ensure_audit(db)
        findings = db.scalar(select(func.count()).select_from(Attribution)) or 0
        pending = db.scalar(select(func.count()).select_from(Attribution).where(Attribution.status == "pending")) or 0
        summary = (
            f"SEED_SUMMARY brand={BRAND} users={users} sources={sources} "
            f"runs={runs} findings={findings} pending={pending}"
        )
        print(summary, flush=True)
        return {
            "users": users,
            "sources": sources,
            "runs": runs,
            "findings": findings,
            "pending": pending,
        }


if __name__ == "__main__":
    seed_all()
