"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "channel.create": "新建渠道",
    "channel.update": "修改渠道预算",
    "run.create": "发起归因运行",
    "run.complete": "归因计算完成",
    "attribution.review": "复核归因结果",
    "export.attributions": "导出归因与预算建议",
    "export.balances": "导出余额台账",
    "billing.post_batch": "账单批次入账",
    "billing.reverse": "账单记录冲正",
    "budget.adjust": "预算调整占用",
    "budget.approve": "批准预算调整",
    "budget.reject": "驳回预算调整",
    "http.mutation": "写请求",
}
