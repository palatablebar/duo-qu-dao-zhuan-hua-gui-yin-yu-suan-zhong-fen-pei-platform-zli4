"""导出服务：归因结果 + 预算建议 CSV。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import CHANNEL_TYPE_LABELS, REVIEW_STATUS_LABELS, RUN_STATUS_LABELS
from src.models.attribution import Attribution
from src.models.attribution_run import AttributionRun
from src.models.channel import Channel
from src.utils.csv_export import to_csv


def attributions_csv(db: Session, run_id: int | None = None) -> bytes:
    stmt = select(Attribution)
    if run_id:
        stmt = stmt.where(Attribution.run_id == run_id)
    rows = db.scalars(stmt.order_by(Attribution.run_id, Attribution.share.desc())).all()
    channels = {row.id: row for row in db.scalars(select(Channel)).all()}
    runs = {row.id: row for row in db.scalars(select(AttributionRun)).all()}
    headers = [
        "运行号", "期间", "渠道", "渠道类型", "归因占比", "last-click占比", "Shapley占比",
        "移除效应", "贡献额", "成本", "ROI", "当前预算", "建议预算", "变动幅度", "复核状态", "复核人",
    ]
    lines = []
    for item in rows:
        channel = channels.get(item.channel_id)
        run = runs.get(item.run_id)
        lines.append(
            [
                run.run_no if run else "",
                run.period if run else "",
                channel.name if channel else "",
                CHANNEL_TYPE_LABELS.get(channel.type, channel.type) if channel else "",
                f"{item.share * 100:.2f}%",
                f"{item.last_click_share * 100:.2f}%",
                f"{item.shapley_share * 100:.2f}%",
                f"{item.removal_effect * 100:.2f}%",
                f"{item.credit_amount:.2f}",
                f"{item.cost:.2f}",
                f"{item.roi:.4f}",
                f"{item.budget:.2f}",
                f"{item.suggested_budget:.2f}",
                f"{item.delta_pct:+.2f}%",
                REVIEW_STATUS_LABELS.get(item.status, item.status),
                item.reviewer or "",
            ]
        )
    return to_csv(headers, lines)


def runs_csv(db: Session) -> bytes:
    runs = db.scalars(select(AttributionRun).order_by(AttributionRun.id)).all()
    headers = ["运行号", "期间", "口径", "状态", "用户数", "触点数", "转化数", "营收", "操作人", "开始时间", "结束时间"]
    lines = [
        [
            run.run_no,
            run.period,
            run.model,
            RUN_STATUS_LABELS.get(run.status, run.status),
            run.users_count,
            run.touchpoints_count,
            run.conversions_count,
            f"{run.revenue:.2f}",
            run.operator_email,
            run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "",
            run.finished_at.strftime("%Y-%m-%d %H:%M") if run.finished_at else "",
        ]
        for run in runs
    ]
    return to_csv(headers, lines)
