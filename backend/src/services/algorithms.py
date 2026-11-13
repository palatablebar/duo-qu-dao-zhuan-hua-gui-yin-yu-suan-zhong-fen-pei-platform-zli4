"""归因与预算重分配算法（纯函数，无 IO、无随机、可单测）。

两个算法：
A. 路径 + 马尔可夫移除效应
   - 用户触点按时间排序 -> 路径（渠道序列 + 是否转化）
   - 全量路径聚合成一阶转移矩阵，含 START / CONVERSION / NULL 三个特殊状态
   - 移除某渠道（进入该渠道的转移改投 NULL）后重算转化吸收概率，下降比例即移除效应
   - 移除效应归一化 -> 贡献占比；同时输出 last-click 占比用于对比
B. 精确 Shapley + 预算重分配
   - 5 个渠道枚举 2^5 个组合 S，v(S) = 只保留 S 时马尔可夫吸收转化概率
   - 精确 Shapley（含全排列权重），Shapley 占比作为预算分配依据
   - ROI = Shapley 贡献额 / 月度成本；新预算 = 总预算 × 新占比
   - 单渠道变动 ≤ ±30%，品牌搜索保底份额
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

START = "^start"
CONVERSION = "^conv"
NULL = "^null"
ABSORBING = (CONVERSION, NULL)
MAX_PATH_LEN = 8


# --------------------------------------------------------------------------
# 路径构建
# --------------------------------------------------------------------------
def build_journeys(touchpoints: Iterable[dict], conversions: Iterable[dict]) -> list[dict]:
    """把触点/转化明细整理成按用户聚合的路径。

    touchpoints: [{"user_id","channel_code","touched_at"}]
    conversions: [{"user_id","amount"}]
    返回: [{"user_id","path":[...],"converted":bool,"revenue":float}]，按 user_id 升序。
    """
    by_user: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in touchpoints:
        by_user[str(row["user_id"])].append((str(row["touched_at"]), str(row["channel_code"])))
    revenue: dict[str, float] = defaultdict(float)
    converted: set[str] = set()
    for row in conversions:
        uid = str(row["user_id"])
        converted.add(uid)
        revenue[uid] += float(row.get("amount") or 0.0)

    journeys: list[dict] = []
    for uid in sorted(by_user):
        ordered = sorted(by_user[uid], key=lambda item: (item[0], item[1]))
        path = [channel for _, channel in ordered]
        journeys.append(
            {
                "user_id": uid,
                "path": path,
                "converted": uid in converted,
                "revenue": round(revenue.get(uid, 0.0), 2),
            }
        )
    return journeys


def build_transitions(journeys: Sequence[dict]) -> dict[tuple[str, str], int]:
    """聚合转移计数：START -> 首个渠道 -> … -> CONVERSION / NULL。"""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for journey in journeys:
        path = [str(channel) for channel in journey["path"]]
        if not path:
            counts[(START, CONVERSION)] += 1
            continue
        counts[(START, path[0])] += 1
        for prev, nxt in zip(path, path[1:]):
            counts[(prev, nxt)] += 1
        counts[(path[-1], CONVERSION if journey["converted"] else NULL)] += 1
    return dict(counts)


def conversion_probability(
    transitions: dict[tuple[str, str], int],
    channels: Sequence[str],
    allowed: Iterable[str] | None = None,
) -> float:
    """在允许的渠道集合下，从 START 出发被 CONVERSION 吸收的概率。

    被移除渠道的所有入边改投 NULL（该部分流量流失），出边丢弃。
    迭代法是确定性的：达到 1e-13 收敛或 500 轮上限后返回。
    """
    keep = set(channels) if allowed is None else {c for c in allowed if c in set(channels)}
    states = [START, *channels, CONVERSION, NULL]
    index = {state: pos for pos, state in enumerate(states)}
    rows: list[list[float]] = [[0.0] * len(states) for _ in states]
    totals = [0.0] * len(states)

    for (src, dst), count in transitions.items():
        if src == START:
            target = dst if (dst in keep or dst in ABSORBING) else NULL
            src_pos = index[START]
        elif src in keep:
            target = dst if (dst in keep or dst in ABSORBING) else NULL
            src_pos = index[src]
        else:
            continue
        if target not in index:
            target = NULL
        rows[src_pos][index[target]] += float(count)
        totals[src_pos] += float(count)

    for pos, total in enumerate(totals):
        if total <= 0:
            continue
        rows[pos] = [value / total for value in rows[pos]]

    values = [0.0] * len(states)
    values[index[CONVERSION]] = 1.0
    start_pos = index[START]
    for _ in range(500):
        delta = 0.0
        for pos, state in enumerate(states):
            if state in ABSORBING:
                continue
            row = rows[pos]
            total = 0.0
            for target_pos, weight in enumerate(row):
                if weight:
                    total += weight * values[target_pos]
            delta = max(delta, abs(total - values[pos]))
            values[pos] = total
        if delta < 1e-13:
            break
    return round(values[start_pos], 10)


def removal_effects(journeys: Sequence[dict], channels: Sequence[str]) -> dict[str, float]:
    """算法 A：每个渠道的移除效应 = (基准转化率 - 移除后转化率) / 基准转化率。"""
    transitions = build_transitions(journeys)
    base = conversion_probability(transitions, channels)
    if base <= 0:
        return {channel: 0.0 for channel in channels}
    effects: dict[str, float] = {}
    for channel in channels:
        keep = [c for c in channels if c != channel]
        without = conversion_probability(transitions, channels, keep)
        effects[channel] = round(max(0.0, (base - without) / base), 10)
    return effects


def last_click_shares(journeys: Sequence[dict], channels: Sequence[str]) -> dict[str, float]:
    """last-click 占比：只看转化路径的最后一个渠道，用于和马尔可夫口径对比。"""
    counts: dict[str, int] = {channel: 0 for channel in channels}
    converted = [journey for journey in journeys if journey["converted"] and journey["path"]]
    for journey in converted:
        last = journey["path"][-1]
        if last in counts:
            counts[last] += 1
    total = len(converted)
    if total == 0:
        return {channel: 0.0 for channel in channels}
    return {channel: round(counts[channel] / total, 10) for channel in channels}


def normalization(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {key: 0.0 for key in values}
    return {key: round(value / total, 10) for key, value in values.items()}


# --------------------------------------------------------------------------
# 算法 B：精确 Shapley
# --------------------------------------------------------------------------
def shapley_values(transitions: dict[tuple[str, str], int], channels: Sequence[str]) -> dict[str, float]:
    """2^n 组合枚举 + 全排列权重，返回精确 Shapley 值（v(∅)=0）。"""
    n = len(channels)
    cache: dict[frozenset[str], float] = {}

    def value(subset: frozenset[str]) -> float:
        if subset not in cache:
            cache[subset] = conversion_probability(transitions, channels, subset)
        return cache[subset]

    weights = [math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n) for k in range(n)]
    result: dict[str, float] = {}
    for channel in channels:
        others = [c for c in channels if c != channel]
        total = 0.0
        for mask in range(1 << len(others)):
            subset = frozenset(others[pos] for pos in range(len(others)) if mask >> pos & 1)
            marginal = value(subset | {channel}) - value(subset)
            total += weights[len(subset)] * marginal
        result[channel] = round(total, 12)
    return result


# --------------------------------------------------------------------------
# 预算重分配
# --------------------------------------------------------------------------
EFFICIENCY_ALPHA = 0.7
MAX_DELTA = 0.30
BRAND_FLOOR_SHARE = 0.12


def reallocate_budget(
    channels: Sequence[dict],
    roi: dict[str, float],
    total_budget: float,
    *,
    alpha: float = EFFICIENCY_ALPHA,
    max_delta: float = MAX_DELTA,
    brand_floor_share: float = BRAND_FLOOR_SHARE,
) -> list[dict]:
    """按 ROI 效率做预算重分配，返回每渠道建议预算。

    步骤：
    1. efficiency = roi / 平均 ROI（总贡献额 / 总成本），权重 = 现有预算 × efficiency^alpha；
    2. 目标预算 = 总预算 × 权重占比；
    3. 品牌搜索保底份额（低于保底则抬到保底）；
    4. 单渠道相对现有预算变动 ≤ ±max_delta（保底优先于上限）；
    5. 注水式迭代：锁定触边渠道，剩余预算按权重分给自由渠道，直至稳定；
    6. 分位四舍五入后把残差补到最大渠道，保证合计等于总预算。
    """
    if not channels:
        return []
    total_budget = round(float(total_budget), 2)
    current = {item["code"]: float(item["budget"]) for item in channels}
    current_total = sum(current.values()) or 1.0
    total_cost = sum(float(item.get("monthly_cost") or 0) for item in channels) or 1.0
    total_credit = sum(float(roi.get(code, 0.0)) * float(item.get("monthly_cost") or 0) for code, item in ((c["code"], c) for c in channels))
    avg_roi = total_credit / total_cost if total_cost else 0.0

    weights: dict[str, float] = {}
    for item in channels:
        code = item["code"]
        roi_value = float(roi.get(code, 0.0))
        efficiency = (roi_value / avg_roi) if avg_roi > 0 else 1.0
        efficiency = min(4.0, max(0.25, efficiency))
        weights[code] = max(1e-6, current[code] * (efficiency**alpha))

    def is_brand(item: dict) -> bool:
        return str(item.get("type")) == "search" and "品牌" in str(item.get("name", ""))

    lower = {code: current[code] * (1.0 - max_delta) for code in current}
    upper = {code: current[code] * (1.0 + max_delta) for code in current}
    for item in channels:
        if is_brand(item):
            floor = total_budget * brand_floor_share
            lower[item["code"]] = max(lower[item["code"]], floor)
            upper[item["code"]] = max(upper[item["code"]], lower[item["code"]])

    weight_total = sum(weights.values()) or 1.0
    target = {code: total_budget * weights[code] / weight_total for code in weights}

    fixed: dict[str, float] = {}
    free = set(current)
    for _ in range(12):
        clamped: dict[str, float] = {}
        for code in list(free):
            if target[code] < lower[code]:
                clamped[code] = lower[code]
            elif target[code] > upper[code]:
                clamped[code] = upper[code]
        if not clamped:
            break
        fixed.update(clamped)
        free -= set(clamped)
        if not free:
            break
        remaining = total_budget - sum(fixed.values())
        free_weight = sum(weights[code] for code in free) or 1.0
        for code in free:
            target[code] = remaining * weights[code] / free_weight

    suggested: dict[str, float] = {}
    for code in current:
        value = fixed.get(code, target[code])
        suggested[code] = round(min(upper[code], max(lower[code], value)), 2)

    residual = round(total_budget - sum(suggested.values()), 2)
    if abs(residual) >= 0.01:
        anchor = max(suggested, key=lambda code: (suggested[code], code))
        suggested[anchor] = round(min(upper[anchor], max(lower[anchor], suggested[anchor] + residual)), 2)

    result: list[dict] = []
    for item in channels:
        code = item["code"]
        value = suggested[code]
        delta = round(value - current[code], 2)
        result.append(
            {
                "code": code,
                "name": item["name"],
                "type": item.get("type"),
                "current_budget": round(current[code], 2),
                "suggested_budget": value,
                "delta": delta,
                "delta_pct": round(delta / current[code] * 100, 2) if current[code] else 0.0,
                "roi": round(float(roi.get(code, 0.0)), 4),
                "efficiency": round(weights[code] / current[code], 4) if current[code] else 0.0,
                "brand_floor": bool(is_brand(item)),
                "current_share": round(current[code] / current_total, 6),
                "suggested_share": round(value / total_budget, 6) if total_budget else 0.0,
            }
        )
    return result


# --------------------------------------------------------------------------
# 路径分布 / 汇总
# --------------------------------------------------------------------------
def path_length_distribution(journeys: Sequence[dict]) -> list[dict]:
    buckets = [
        {"key": "1", "label": "1 触点", "count": 0, "converted": 0},
        {"key": "2", "label": "2 触点", "count": 0, "converted": 0},
        {"key": "3", "label": "3 触点", "count": 0, "converted": 0},
        {"key": "4", "label": "4 触点", "count": 0, "converted": 0},
        {"key": "5+", "label": "5+ 触点", "count": 0, "converted": 0},
    ]
    for journey in journeys:
        length = len(journey["path"])
        pos = min(length, 5) - 1
        if pos < 0:
            continue
        buckets[pos]["count"] += 1
        if journey["converted"]:
            buckets[pos]["converted"] += 1
    for bucket in buckets:
        bucket["rate"] = round(bucket["converted"] / bucket["count"], 4) if bucket["count"] else 0.0
    return buckets


def summarize(journeys: Sequence[dict], channels: Sequence[str]) -> dict:
    """完整算法 A/B 结果（不落库，供运行服务与单测共用）。"""
    transitions = build_transitions(journeys)
    base_probability = conversion_probability(transitions, channels)
    effects = removal_effects(journeys, channels)
    markov = normalization(effects)
    last_click = last_click_shares(journeys, channels)
    shapley = shapley_values(transitions, channels)
    shapley_total = sum(shapley.values())
    shapley_share = (
        {channel: round(value / shapley_total, 10) for channel, value in shapley.items()}
        if shapley_total > 0
        else {channel: 0.0 for channel in channels}
    )
    converted = [journey for journey in journeys if journey["converted"]]
    revenue = round(sum(journey["revenue"] for journey in converted), 2)
    return {
        "channels": list(channels),
        "users": len(journeys),
        "touchpoints": sum(len(journey["path"]) for journey in journeys),
        "conversions": len(converted),
        "revenue": revenue,
        "conversion_probability": base_probability,
        "conversion_rate": round(len(converted) / len(journeys), 6) if journeys else 0.0,
        "avg_path_length": round(sum(len(j["path"]) for j in journeys) / len(journeys), 4) if journeys else 0.0,
        "removal_effects": effects,
        "markov_share": markov,
        "last_click_share": last_click,
        "shapley": {channel: round(value, 12) for channel, value in shapley.items()},
        "shapley_share": shapley_share,
        "path_length": path_length_distribution(journeys),
    }
