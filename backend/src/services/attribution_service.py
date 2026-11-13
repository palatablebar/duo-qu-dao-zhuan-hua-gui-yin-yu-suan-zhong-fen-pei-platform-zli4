"""归因服务：运行编排、结果持久化、预算方案与复核。

算法本体在 services/algorithms.py（纯函数）；本模块只负责取数、落库、序列化。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    ATTRIBUTION_MODEL_LABELS,
    CHANNEL_TYPE_LABELS,
    REVIEW_STATUS_LABELS,
    RUN_STATUS_LABELS,
    TRIGGER_LABELS,
)
from src.models.attribution import Attribution
from src.models.attribution_run import AttributionRun
from src.models.channel import Channel
from src.models.conversion import Conversion
from src.models.touchpoint import Touchpoint
from src.services import algorithms
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, local_now, utcnow


def serialize_run(run: AttributionRun) -> dict:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "period": run.period,
        "model": run.model,
        "model_label": ATTRIBUTION_MODEL_LABELS.get(run.model, run.model),
        "trigger": run.trigger,
        "trigger_label": TRIGGER_LABELS.get(run.trigger, run.trigger),
        "status": run.status,
        "status_label": RUN_STATUS_LABELS.get(run.status, run.status),
        "operator_email": run.operator_email,
        "users_count": run.users_count,
        "touchpoints_count": run.touchpoints_count,
        "conversions_count": run.conversions_count,
        "revenue": round(float(run.revenue), 2),
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def serialize_attribution(row: Attribution, channel: Channel | None, run: AttributionRun | None = None, hide_costs: bool = False) -> dict:
    payload = {
        "id": row.id,
        "run_id": row.run_id,
        "run_no": run.run_no if run else None,
        "period": run.period if run else None,
        "channel_id": row.channel_id,
        "channel_code": channel.code if channel else None,
        "channel_name": channel.name if channel else None,
        "channel_type": channel.type if channel else None,
        "channel_type_label": CHANNEL_TYPE_LABELS.get(channel.type, channel.type) if channel else None,
        "share": round(float(row.share), 6),
        "markov_share": round(float(row.markov_share), 6),
        "last_click_share": round(float(row.last_click_share), 6),
        "shapley_share": round(float(row.shapley_share), 6),
        "removal_effect": round(float(row.removal_effect), 6),
        "status": row.status,
        "status_label": REVIEW_STATUS_LABELS.get(row.status, row.status),
        "reviewer": row.reviewer,
        "review_note": row.review_note,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
        "costs_hidden": hide_costs,
        "credit_amount": None if hide_costs else round(float(row.credit_amount), 2),
        "roi": None if hide_costs else round(float(row.roi), 4),
        "cost": None if hide_costs else round(float(row.cost), 2),
        "budget": None if hide_costs else round(float(row.budget), 2),
        "suggested_budget": None if hide_costs else round(float(row.suggested_budget), 2),
        "delta_pct": None if hide_costs else round(float(row.delta_pct), 2),
    }
    return payload


def next_run_no(db: Session) -> str:
    prefix = f"MC{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(AttributionRun).where(AttributionRun.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def execute_run(db: Session, run: AttributionRun) -> AttributionRun:
    """取全量触点/转化 -> 路径 -> 马尔可夫 + Shapley -> 落 5 条 Attribution。"""
    run.status = "running"
    channels = db.scalars(select(Channel).where(Channel.enabled.is_(True)).order_by(Channel.id)).all()
    if not channels:
        run.status = "failed"
        run.log_text = "没有启用的渠道，无法归因"
        run.finished_at = utcnow()
        db.flush()
        return run
    code_by_id = {channel.id: channel.code for channel in channels}
    touchpoints = db.scalars(select(Touchpoint).order_by(Touchpoint.touched_at, Touchpoint.id)).all()
    conversions = db.scalars(select(Conversion).order_by(Conversion.converted_at)).all()
    tp_rows = [
        {"user_id": row.user_id, "channel_code": code_by_id.get(row.channel_id, ""), "touched_at": row.touched_at.isoformat()}
        for row in touchpoints
        if row.channel_id in code_by_id
    ]
    cv_rows = [{"user_id": row.user_id, "amount": row.amount} for row in conversions]
    codes = [channel.code for channel in channels]
    journeys = algorithms.build_journeys(tp_rows, cv_rows)
    summary = algorithms.summarize(journeys, codes)

    revenue = summary["revenue"]
    cost_by_code = {channel.code: float(channel.monthly_cost) for channel in channels}
    budget_by_code = {channel.code: float(channel.budget) for channel in channels}
    shapley_credit = {code: summary["shapley_share"][code] * revenue for code in codes}
    roi = {code: round(shapley_credit[code] / cost_by_code[code], 6) if cost_by_code[code] else 0.0 for code in codes}
    total_budget = round(sum(budget_by_code.values()), 2)
    channel_specs = [
        {
            "code": channel.code,
            "name": channel.name,
            "type": channel.type,
            "monthly_cost": float(channel.monthly_cost),
            "budget": float(channel.budget),
        }
        for channel in channels
    ]
    plan = algorithms.reallocate_budget(channel_specs, roi, total_budget)
    plan_by_code = {item["code"]: item for item in plan}

    for channel in channels:
        code = channel.code
        existing = db.scalar(select(Attribution).where(Attribution.run_id == run.id, Attribution.channel_id == channel.id))
        values = {
            "share": summary["markov_share"][code],
            "markov_share": summary["markov_share"][code],
            "last_click_share": summary["last_click_share"][code],
            "shapley_share": summary["shapley_share"][code],
            "removal_effect": summary["removal_effects"][code],
            "credit_amount": round(summary["markov_share"][code] * revenue, 2),
            "roi": roi[code],
            "cost": round(cost_by_code[code], 2),
            "budget": round(budget_by_code[code], 2),
            "suggested_budget": plan_by_code[code]["suggested_budget"],
            "delta_pct": plan_by_code[code]["delta_pct"],
            "payload": {
                "last_click_credit": round(summary["last_click_share"][code] * revenue, 2),
                "markov_credit": round(summary["markov_share"][code] * revenue, 2),
                "shapley_credit": round(shapley_credit[code], 2),
                "removal_effect": summary["removal_effects"][code],
                "efficiency": plan_by_code[code]["efficiency"],
                "brand_floor": plan_by_code[code]["brand_floor"],
                "total_revenue": revenue,
            },
        }
        if existing is None:
            db.add(Attribution(run_id=run.id, channel_id=channel.id, status="pending", **values))
        else:
            for key, value in values.items():
                setattr(existing, key, value)

    ranked = sorted(roi.items(), key=lambda item: (-item[1], item[0]))
    metrics = {
        "users": summary["users"],
        "touchpoints": summary["touchpoints"],
        "conversions": summary["conversions"],
        "conversion_rate": summary["conversion_rate"],
        "conversion_probability": summary["conversion_probability"],
        "avg_path_length": summary["avg_path_length"],
        "revenue": revenue,
        "total_cost": round(sum(cost_by_code.values()), 2),
        "total_budget": total_budget,
        "path_length": summary["path_length"],
        "markov_share": summary["markov_share"],
        "last_click_share": summary["last_click_share"],
        "shapley_share": summary["shapley_share"],
        "removal_effects": summary["removal_effects"],
        "roi": roi,
        "roi_rank": [code for code, _ in ranked],
        "plan": [
            {
                "code": item["code"],
                "name": item["name"],
                "current_budget": item["current_budget"],
                "suggested_budget": item["suggested_budget"],
                "delta_pct": item["delta_pct"],
            }
            for item in plan
        ],
        "policy": {
            "efficiency_alpha": algorithms.EFFICIENCY_ALPHA,
            "max_delta": algorithms.MAX_DELTA,
            "brand_floor_share": algorithms.BRAND_FLOOR_SHARE,
        },
    }
    run.metrics = metrics
    run.users_count = summary["users"]
    run.touchpoints_count = summary["touchpoints"]
    run.conversions_count = summary["conversions"]
    run.revenue = revenue
    run.status = "success" if summary["users"] else "partial"
    content = summary["markov_share"].get("content", 0.0)
    last_content = summary["last_click_share"].get("content", 0.0)
    plan_text = ", ".join(
        "{name} {delta:+.2f}%".format(name=item["name"], delta=item["delta_pct"]) for item in plan
    )
    run.log_text = "\n".join(
        [
            "路径构建：{users} 用户 / {tp} 触点 / {cv} 转化".format(
                users=summary["users"], tp=summary["touchpoints"], cv=summary["conversions"]
            ),
            "马尔可夫基准吸收转化率：{rate:.2f}%".format(rate=summary["conversion_probability"] * 100),
            "内容种草：last-click {last:.2f}% → 马尔可夫 {markov:.2f}%".format(
                last=last_content * 100, markov=content * 100
            ),
            "Shapley 精确枚举 2^{n} = {total} 个渠道组合".format(n=len(codes), total=2 ** len(codes)),
            "预算建议：" + plan_text,
        ]
    )
    run.finished_at = utcnow()
    db.flush()
    return run

def create_and_execute(
    db: Session,
    *,
    period: str,
    model: str,
    trigger: str,
    operator_email: str,
    seed_key: str | None = None,
) -> AttributionRun:
    if seed_key:
        existing = db.scalar(select(AttributionRun).where(AttributionRun.seed_key == seed_key))
        if existing is not None:
            return existing
    run = AttributionRun(
        run_no=next_run_no(db),
        period=period,
        model=model,
        trigger=trigger,
        status="running",
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(run)
    db.flush()
    return execute_run(db, run)


def list_runs(db: Session, status: str | None, limit: int, offset: int) -> dict:
    stmt = select(AttributionRun)
    count_stmt = select(func.count()).select_from(AttributionRun)
    if status:
        stmt = stmt.where(AttributionRun.status == status)
        count_stmt = count_stmt.where(AttributionRun.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AttributionRun.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [serialize_run(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_run(db: Session, run_id: int) -> AttributionRun:
    run = db.get(AttributionRun, run_id)
    if run is None:
        raise AppError("NOT_FOUND", 404, {"entity": "attribution_run", "id": run_id})
    return run


def latest_run(db: Session) -> AttributionRun | None:
    return db.scalar(select(AttributionRun).order_by(AttributionRun.id.desc()).limit(1))


def list_attributions(
    db: Session,
    *,
    run_id: int | None = None,
    status: str | None = None,
    hide_costs: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(Attribution)
    count_stmt = select(func.count()).select_from(Attribution)
    if run_id:
        stmt = stmt.where(Attribution.run_id == run_id)
        count_stmt = count_stmt.where(Attribution.run_id == run_id)
    if status:
        stmt = stmt.where(Attribution.status == status)
        count_stmt = count_stmt.where(Attribution.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Attribution.share.desc(), Attribution.id).limit(limit).offset(offset)).all()
    channels = {row.id: row for row in db.scalars(select(Channel)).all()}
    runs = {row.id: row for row in db.scalars(select(AttributionRun)).all()}
    return {
        "items": [serialize_attribution(row, channels.get(row.channel_id), runs.get(row.run_id), hide_costs) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_attribution(db: Session, attribution_id: int) -> Attribution:
    row = db.get(Attribution, attribution_id)
    if row is None:
        raise AppError("NOT_FOUND", 404, {"entity": "attribution", "id": attribution_id})
    return row


def review(db: Session, row: Attribution, *, status: str, note: str | None, reviewer: str) -> Attribution:
    row.status = status
    row.review_note = note
    row.reviewer = reviewer
    row.updated_at = utcnow()
    db.flush()
    return row


def plan_for_run(db: Session, run: AttributionRun, hide_costs: bool = False) -> dict:
    """预算重分配方案：基于运行时的预算快照重算，保证可复现。"""
    rows = db.scalars(select(Attribution).where(Attribution.run_id == run.id)).all()
    channels = {row.id: row for row in db.scalars(select(Channel)).all()}
    channel_specs = []
    roi = {}
    for row in rows:
        channel = channels.get(row.channel_id)
        if channel is None:
            continue
        channel_specs.append(
            {
                "code": channel.code,
                "name": channel.name,
                "type": channel.type,
                "monthly_cost": float(row.cost),
                "budget": float(row.budget),
            }
        )
        roi[channel.code] = float(row.roi)
    total_budget = round(sum(item["budget"] for item in channel_specs), 2)
    plan = algorithms.reallocate_budget(channel_specs, roi, total_budget)
    by_code = {item["code"]: item for item in plan}
    items = []
    for row in sorted(rows, key=lambda item: -float(item.share)):
        channel = channels.get(row.channel_id)
        if channel is None:
            continue
        item = by_code.get(channel.code, {})
        items.append(
            {
                "attribution_id": row.id,
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
                "current_budget": None if hide_costs else round(float(item.get("current_budget", row.budget)), 2),
                "suggested_budget": None if hide_costs else round(float(item.get("suggested_budget", row.suggested_budget)), 2),
                "delta": None if hide_costs else round(float(item.get("delta", 0.0)), 2),
                "delta_pct": None if hide_costs else round(float(item.get("delta_pct", row.delta_pct)), 2),
                "status": row.status,
                "status_label": REVIEW_STATUS_LABELS.get(row.status, row.status),
                "review_note": row.review_note,
            }
        )
    return {
        "run_id": run.id,
        "run_no": run.run_no,
        "period": run.period,
        "status": run.status,
        "total_budget": None if hide_costs else total_budget,
        "costs_hidden": hide_costs,
        "policy": {
            "efficiency_alpha": algorithms.EFFICIENCY_ALPHA,
            "max_delta": algorithms.MAX_DELTA,
            "brand_floor_share": algorithms.BRAND_FLOOR_SHARE,
        },
        "items": items,
    }
