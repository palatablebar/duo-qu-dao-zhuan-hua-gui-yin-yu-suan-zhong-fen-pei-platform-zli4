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
