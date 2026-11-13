"""Celery 任务：worker 心跳 + 每日复盘（对当前月份重跑一次归因）。"""
from __future__ import annotations

import time

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_refresh() -> dict:
    """每天 07:40 对当月重跑一次归因，留下 scheduler 审计记录。"""
    from src.config.database import session_scope
    from src.services import attribution_service, audit_service
    from src.utils.timeutil import local_now

    period = f"{local_now():%Y-%m}"
    operator = "scheduler@" + settings.app_name + ".io"
    run_no = ""
    status = "skipped"
    with session_scope() as db:
        run = attribution_service.create_and_execute(
            db, period=period, model="markov", trigger="schedule", operator_email=operator
        )
        audit_service.record(
            db,
            actor_email=operator,
            actor_role="admin",
            action="run.create",
            entity="attribution_run",
            entity_id=run.id,
            detail={"trigger": "schedule", "run_no": run.run_no, "period": period},
            layer="worker",
        )
        run_no, status = run.run_no, run.status
    logger.info("daily attribution refresh finished: %s %s", run_no, status)
    return {"run_no": run_no, "status": status}
