"""总览：转化率、路径长度分布、口径对比、最近运行、worker 心跳。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import CHANNEL_TYPE_LABELS, REVIEW_STATUS_LABELS, RUN_STATUS_LABELS
from src.models.attribution import Attribution
from src.models.attribution_run import AttributionRun
from src.models.channel import Channel
from src.models.conversion import Conversion
from src.models.touchpoint import Touchpoint
from src.services import attribution_service, algorithms
from src.utils.timeutil import local_now, utcnow


def worker_alive() -> bool:
    try:
        import time

        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def _live_summary(db: Session) -> dict:
    channels = db.scalars(select(Channel).order_by(Channel.id)).all()
    code_by_id = {channel.id: channel.code for channel in channels}
    touchpoints = db.scalars(select(Touchpoint).order_by(Touchpoint.touched_at, Touchpoint.id)).all()
    conversions = db.scalars(select(Conversion)).all()
    rows = [
        {"user_id": row.user_id, "channel_code": code_by_id.get(row.channel_id, ""), "touched_at": row.touched_at.isoformat()}
        for row in touchpoints
        if row.channel_id in code_by_id
    ]
    journeys = algorithms.build_journeys(rows, [{"user_id": row.user_id, "amount": row.amount} for row in conversions])
    codes = [channel.code for channel in channels]
    return algorithms.summarize(journeys, codes) if codes else {"path_length": [], "markov_share": {}, "last_click_share": {}}


def overview(db: Session, hide_costs: bool = False) -> dict:
    channels = db.scalars(select(Channel).order_by(Channel.id)).all()
    runs_total = db.scalar(select(func.count()).select_from(AttributionRun)) or 0
    attributions_total = db.scalar(select(func.count()).select_from(Attribution)) or 0
    pending_total = db.scalar(select(func.count()).select_from(Attribution).where(Attribution.status == "pending")) or 0
    latest = attribution_service.latest_run(db)
    live = _live_summary(db)

    metrics = (latest.metrics or {}) if latest else {}
    path_length = metrics.get("path_length") or live.get("path_length") or []
    status_rows = db.execute(select(Attribution.status, func.count()).group_by(Attribution.status)).all()

    since = utcnow() - timedelta(days=7)
    recent = db.scalars(select(AttributionRun).where(AttributionRun.started_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for run in recent
            if run.started_at
            and (run.started_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "runs": count})

    rows = db.scalars(select(Attribution).where(Attribution.run_id == latest.id)).all() if latest else []
    channel_map = {channel.id: channel for channel in channels}
    comparison = []
    for row in sorted(rows, key=lambda item: -float(item.share)):
        channel = channel_map.get(row.channel_id)
        if channel is None:
            continue
        comparison.append(
            {
                "channel_id": channel.id,
                "channel_code": channel.code,
                "channel_name": channel.name,
                "channel_type": channel.type,
                "channel_type_label": CHANNEL_TYPE_LABELS.get(channel.type, channel.type),
                "share": round(float(row.share), 6),
                "last_click_share": round(float(row.last_click_share), 6),
                "shapley_share": round(float(row.shapley_share), 6),
                "roi": None if hide_costs else round(float(row.roi), 4),
                "cost": None if hide_costs else round(float(row.cost), 2),
                "suggested_budget": None if hide_costs else round(float(row.suggested_budget), 2),
                "delta_pct": None if hide_costs else round(float(row.delta_pct), 2),
            }
        )
    biggest_gap = None
    if comparison:
        biggest_gap = max(comparison, key=lambda item: item["share"] - item["last_click_share"])

    channel_rows = []
    for channel in channels:
        channel_rows.append(
            {
                "id": channel.id,
                "code": channel.code,
                "name": channel.name,
                "type": channel.type,
                "type_label": CHANNEL_TYPE_LABELS.get(channel.type, channel.type),
                "owner": channel.owner,
                "enabled": channel.enabled,
                "monthly_cost": None if hide_costs else round(float(channel.monthly_cost), 2),
                "budget": None if hide_costs else round(float(channel.budget), 2),
            }
        )

    return {
        "brand": settings.app_name,
        "period": latest.period if latest else None,
        "channels_total": len(channels),
        "runs_total": runs_total,
        "attributions_total": attributions_total,
        "pending_total": pending_total,
        "worker_alive": worker_alive(),
        "costs_hidden": hide_costs,
        "totals": {
            "users": metrics.get("users") or live.get("users", 0),
            "touchpoints": metrics.get("touchpoints") or live.get("touchpoints", 0),
            "conversions": metrics.get("conversions") or live.get("conversions", 0),
            "conversion_rate": metrics.get("conversion_rate") or live.get("conversion_rate", 0.0),
            "avg_path_length": metrics.get("avg_path_length") or live.get("avg_path_length", 0.0),
            "revenue": None if hide_costs else round(float(metrics.get("revenue") or live.get("revenue") or 0.0), 2),
            "total_budget": None if hide_costs else round(float(metrics.get("total_budget") or 0.0), 2),
        },
        "conversion_probability": metrics.get("conversion_probability") or live.get("conversion_probability", 0.0),
        "path_length": path_length,
        "comparison": comparison,
        "biggest_gap": biggest_gap,
        "channels": channel_rows,
        "review": [
            {
                "key": key,
                "label": REVIEW_STATUS_LABELS.get(key, key),
                "count": count,
            }
            for key, count in sorted(status_rows)
        ],
        "trend": trend,
        "latest_run": attribution_service.serialize_run(latest) if latest else None,
        "run_status": [
            {"key": key, "label": label} for key, label in RUN_STATUS_LABELS.items()
        ],
    }
