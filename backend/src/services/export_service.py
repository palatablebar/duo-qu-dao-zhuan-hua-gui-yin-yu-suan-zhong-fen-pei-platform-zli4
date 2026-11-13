"""导出服务：归因结果 + 预算建议 + 余额台账 CSV。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import BILL_KIND_LABELS, CHANNEL_TYPE_LABELS, REVIEW_STATUS_LABELS, RUN_STATUS_LABELS
from src.models.attribution import Attribution
from src.models.attribution_run import AttributionRun
from src.models.billing import BillBatch, BillEntry
from src.models.channel import Channel
from src.services import billing_service
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


def balances_csv(db: Session) -> bytes:
    """余额台账：与页面 /api/billing/overview 共用 channel_balances()，保证导出与页面一致。"""
    data = billing_service.channel_balances(db)
    headers = ["渠道编码", "渠道名称", "渠道类型", "月度预算", "净消耗", "在途占用", "可用余额"]
    lines = [
        [
            item["code"],
            item["name"],
            item["type_label"],
            f"{item['budget']:.2f}",
            f"{item['net_spend']:.2f}",
            f"{item['held']:.2f}",
            f"{item['available']:.2f}",
        ]
        for item in data["items"]
    ]
    totals = data["totals"]
    lines.append(
        [
            "合计",
            "",
            "",
            f"{totals['budget']:.2f}",
            f"{totals['net_spend']:.2f}",
            f"{totals['held']:.2f}",
            f"{totals['available']:.2f}",
        ]
    )
    return to_csv(headers, lines)


def bill_entries_csv(db: Session) -> bytes:
    rows = db.scalars(select(BillEntry).order_by(BillEntry.id)).all()
    batches = {row.id: row for row in db.scalars(select(BillBatch)).all()}
    channels = {row.id: row for row in db.scalars(select(Channel)).all()}
    entries_by_id = {row.id: row for row in rows}
    headers = ["批次号", "行号", "账期", "渠道", "类型", "金额", "冲正指向", "备注", "操作人", "入账时间"]
    lines = []
    for entry in rows:
        batch = batches.get(entry.batch_id)
        channel = channels.get(entry.channel_id)
        reversed_entry = entries_by_id.get(entry.reverses_id) if entry.reverses_id else None
        lines.append(
            [
                batch.batch_no if batch else "",
                entry.row_no,
                batch.period if batch else "",
                channel.name if channel else "",
                BILL_KIND_LABELS.get(entry.kind, entry.kind),
                f"{entry.amount:.2f}",
                reversed_entry.entry_no if reversed_entry else "",
                entry.memo or "",
                batch.created_by if batch else "",
                entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "",
            ]
        )
    return to_csv(headers, lines)
