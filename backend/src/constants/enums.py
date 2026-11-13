"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class ChannelType(StrEnum):
    """投放渠道类型（决定看板分组与预算保底规则）。"""

    SEARCH = "search"
    FEED = "feed"
    CONTENT = "content"
    COMMUNITY = "community"
    LIVE = "live"


CHANNEL_TYPE_LABELS: dict[str, str] = {
    ChannelType.SEARCH.value: "搜索",
    ChannelType.FEED.value: "信息流",
    ChannelType.CONTENT.value: "内容种草",
    ChannelType.COMMUNITY.value: "私域",
    ChannelType.LIVE.value: "直播",
}


class AttributionModel(StrEnum):
    """归因口径：马尔可夫移除效应 / last-click 对照 / Shapley 预算口径。"""

    MARKOV = "markov"
    LAST_CLICK = "last_click"
    SHAPLEY = "shapley"


ATTRIBUTION_MODEL_LABELS: dict[str, str] = {
    AttributionModel.MARKOV.value: "马尔可夫移除效应",
    AttributionModel.LAST_CLICK.value: "last-click 对照",
    AttributionModel.SHAPLEY.value: "精确 Shapley",
}


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


RUN_STATUS_LABELS: dict[str, str] = {
    RunStatus.QUEUED.value: "排队中",
    RunStatus.RUNNING.value: "执行中",
    RunStatus.SUCCESS.value: "成功",
    RunStatus.PARTIAL.value: "部分成功",
    RunStatus.FAILED.value: "失败",
}


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


REVIEW_STATUS_LABELS: dict[str, str] = {
    ReviewStatus.PENDING.value: "待复核",
    ReviewStatus.CONFIRMED.value: "已确认",
    ReviewStatus.DISMISSED.value: "已驳回",
}

REVIEW_STATUS_ORDER: list[str] = [
    ReviewStatus.PENDING.value,
    ReviewStatus.CONFIRMED.value,
    ReviewStatus.DISMISSED.value,
]


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动",
    TriggerKind.SCHEDULE.value: "定时",
    TriggerKind.SEED.value: "初始化",
}


class BillEntryKind(StrEnum):
    """台账分录类型：消耗（+）/ 退款（−）/ 冲正（−原分录）。"""

    SPEND = "spend"
    REFUND = "refund"
    REVERSAL = "reversal"


BILL_KIND_LABELS: dict[str, str] = {
    BillEntryKind.SPEND.value: "消耗",
    BillEntryKind.REFUND.value: "退款",
    BillEntryKind.REVERSAL.value: "冲正",
}


class BillBatchKind(StrEnum):
    """批次类型：入账批次 / 冲正批次（一条冲正分录自成一个批次）。"""

    ENTRY = "entry"
    REVERSAL = "reversal"


BILL_BATCH_KIND_LABELS: dict[str, str] = {
    BillBatchKind.ENTRY.value: "入账",
    BillBatchKind.REVERSAL.value: "冲正",
}


class BillBatchStatus(StrEnum):
    """批次结果：整批入账或整批失败，不存在部分写入。"""

    POSTED = "posted"
    FAILED = "failed"


BILL_BATCH_STATUS_LABELS: dict[str, str] = {
    BillBatchStatus.POSTED.value: "已入账",
    BillBatchStatus.FAILED.value: "入账失败",
}


class AdjustStatus(StrEnum):
    """预算调整状态机：held（在途占用）→ approved / rejected，终态不可逆。"""

    HELD = "held"
    APPROVED = "approved"
    REJECTED = "rejected"


ADJUST_STATUS_LABELS: dict[str, str] = {
    AdjustStatus.HELD.value: "在途占用",
    AdjustStatus.APPROVED.value: "已批准",
    AdjustStatus.REJECTED.value: "已驳回",
}
