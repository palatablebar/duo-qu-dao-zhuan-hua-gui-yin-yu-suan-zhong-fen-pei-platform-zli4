"""演示数据生成器（确定性，无随机源、无网络）。

规模契约（batch-plan gb-608）：
  5 渠道 / 2,400 用户 / 8,600 触点 / 640 转化 / 1 次归因运行 / 5 条 Attribution。

用户编号 1..2400，`index % 15 in {0,1,2,3}` 恰好 640 个转化用户（160 × 4）。
路径由「转化路径原型 / 未转化路径原型」按权重轮转生成，触点总量不足 8600 时
按用户轮询补齐重复触点（同一渠道的二次曝光），保证每次运行逐字一致。
"""
from __future__ import annotations

from collections import Counter

TOTAL_USERS = 2400
TOTAL_TOUCHPOINTS = 8600
TOTAL_CONVERSIONS = 640
PERIOD = "2026-10"
BRAND = "mixcredit"
ORG = "清野日化 · 增长组"

CHANNELS = [
    {
        "code": "brand_search",
        "name": "品牌搜索",
        "type": "search",
        "monthly_cost": 120000.0,
        "budget": 120000.0,
        "owner": "程澜 · 品牌投放",
        "note": "品牌词与品类词竞价，转化确定性最高，按季度锁预算。",
    },
    {
        "code": "feed",
        "name": "效果信息流",
        "type": "feed",
        "monthly_cost": 240000.0,
        "budget": 240000.0,
        "owner": "罗一舟 · 效果投放",
        "note": "抖快信息流为主，CPM 波动大，按周调出价。",
    },
    {
        "code": "content",
        "name": "内容种草",
        "type": "content",
        "monthly_cost": 180000.0,
        "budget": 180000.0,
        "owner": "苏晚 · 内容营销",
        "note": "小红书 KOC 图文 + 短视频测评，多为首触，last-click 长期被低估。",
    },
    {
        "code": "community",
        "name": "私域社群",
        "type": "community",
        "monthly_cost": 90000.0,
        "budget": 90000.0,
        "owner": "何田 · 私域运营",
        "note": "企微社群与老客复购，成本低但触点集中在转化末端。",
    },
    {
        "code": "live",
        "name": "达人直播",
        "type": "live",
        "monthly_cost": 170000.0,
        "budget": 170000.0,
        "owner": "孟晓 · 直播商务",
        "note": "坑位费 + 佣金，单场爆发强，退单率需要单独看。",
    },
]

CHANNEL_CODES = [item["code"] for item in CHANNELS]
CHANNEL_BY_CODE = {item["code"]: item for item in CHANNELS}

CAMPAIGNS = {
    "brand_search": ["品牌词-双11预热", "品类词-洗衣凝珠", "品牌词-日常"],
    "feed": ["信息流-焕新季", "信息流-拉新A", "信息流-复购包"],
    "content": ["小红书-KOC测评", "抖音-家清好物", "小红书-换季收纳"],
    "community": ["企微社群-会员日", "企微社群-老客回访"],
    "live": ["直播-达人选品", "直播-专场返场"],
}

# 转化路径原型（渠道序列，最后一步即 last-click），权重为整数配比
CONVERTED_ARCHETYPES = [
    (["content", "feed", "brand_search"], 8),
    (["content", "brand_search"], 5),
    (["feed", "content", "brand_search"], 4),
    (["feed", "brand_search"], 1),
    (["live", "brand_search"], 1),
    (["content", "community", "feed", "brand_search"], 4),
    (["feed", "content", "community", "brand_search"], 5),
    (["community", "live", "content", "brand_search"], 4),
    (["live", "content", "brand_search"], 4),
    (["content", "feed", "live", "brand_search"], 4),
    (["feed", "live", "content", "brand_search"], 4),
    (["content", "feed", "community", "live", "brand_search"], 4),
    (["content"], 1),
    (["feed", "content"], 2),
    (["content", "community", "feed", "content"], 2),
    (["live", "community", "content"], 2),
    (["content", "feed", "live", "content"], 2),
    (["content", "community", "feed"], 2),
    (["live", "content", "feed"], 2),
    (["brand_search", "content", "community", "feed"], 2),
    (["live", "feed"], 2),
    (["feed", "content", "live"], 2),
    (["community", "content", "feed", "live"], 2),
    (["content", "feed", "content", "live"], 2),
    (["feed", "content", "community"], 2),
    (["content", "feed", "brand_search", "community"], 2),
    (["live", "content", "feed", "community"], 2),
    (["content", "community"], 1),
]

# 未转化路径原型（停在 NULL），权重为整数配比
NULL_ARCHETYPES = [
    (["content"], 12),
    (["feed"], 8),
    (["brand_search"], 6),
    (["live"], 4),
    (["content", "feed"], 8),
    (["feed", "community"], 5),
    (["live", "content"], 5),
    (["community", "feed"], 5),
    (["brand_search", "content"], 4),
    (["feed", "brand_search", "community"], 5),
    (["content", "feed", "community"], 6),
    (["live", "content", "feed"], 5),
    (["community", "feed", "content"], 5),
    (["feed", "content", "live"], 4),
    (["brand_search", "feed", "brand_search"], 4),
    (["content", "feed", "live", "community"], 5),
    (["live", "community", "content", "feed"], 4),
    (["brand_search", "content", "feed"], 4),
    (["content", "feed", "brand_search", "community"], 4),
    (["live", "feed", "content", "community"], 3),
    (["feed", "live", "content", "feed"], 3),
    (["community", "content", "brand_search"], 3),
    (["content", "live"], 3),
    (["feed", "brand_search", "feed", "content"], 3),
    (["brand_search", "community", "feed"], 3),
    (["content", "feed", "live", "brand_search", "community"], 3),
    (["feed", "content", "community", "live", "feed"], 3),
    (["brand_search", "feed", "live", "content", "community"], 2),
]


class Rng:
    """xorshift32：跨 Python 版本逐位一致，不依赖 random 模块实现。"""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = (seed or 1) & 0xFFFFFFFF

    def next_int(self) -> int:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state

    def below(self, bound: int) -> int:
        return self.next_int() % bound

    def pick(self, seq):
        return seq[self.below(len(seq))]


def _weighted_pick(rng: Rng, archetypes: list[tuple[list[str], int]]) -> list[str]:
    total = sum(weight for _, weight in archetypes)
    point = rng.below(total)
    running = 0
    for path, weight in archetypes:
        running += weight
        if point < running:
            return list(path)
    return list(archetypes[-1][0])


def _apply_repeat(path: list[str], channel: str, keep_last: bool) -> list[str]:
    """补触点：把重复曝光插在第一次出现之后；转化路径不移到最后一位，保持 last-click 口径。"""
    if channel not in path:
        return path + [channel]
    pos = path.index(channel)
    if keep_last and pos == len(path) - 1:
        pos = max(0, len(path) - 2)
    return path[: pos + 1] + [channel] + path[pos + 1 :]


def build_dataset() -> dict:
    rng = Rng(6082026)
    converted_users = {index for index in range(1, TOTAL_USERS + 1) if index % 15 in (0, 1, 2, 3)}

    paths: dict[int, list[str]] = {}
    for index in range(1, TOTAL_USERS + 1):
        if index in converted_users:
            path = _weighted_pick(rng, CONVERTED_ARCHETYPES)
        else:
            path = _weighted_pick(rng, NULL_ARCHETYPES)
        paths[index] = path

    # 先按目标基准量把路径拉长到 ~8,100（多触点用户的自然二次触达），
    # 再用「每人最多补 1 条」的方式精确补到 8,600，避免短路径被补成长路径。
    base_target = 8100
    growable = [index for index in range(1, TOTAL_USERS + 1) if len(paths[index]) >= 2]
    total = sum(len(path) for path in paths.values())
    step = 0
    while total < base_target and growable:
        user = growable[(step * 7919) % len(growable)]
        path = paths[user]
        channel = path[(step + len(path)) % len(path)]
        paths[user] = _apply_repeat(path, channel, keep_last=user in converted_users)
        total += 1
        step += 1

    pads = [index for index in range(1, TOTAL_USERS + 1) if len(paths[index]) >= 3]
    step = 0
    while total < TOTAL_TOUCHPOINTS and pads:
        user = pads[(step * 6151) % len(pads)]
        path = paths[user]
        channel = path[(step + len(path)) % len(path)]
        paths[user] = _apply_repeat(path, channel, keep_last=user in converted_users)
        total += 1
        step += 1

    touchpoints: list[dict] = []
    conversions: list[dict] = []
    channel_counter: Counter = Counter()
    serial = 0
    for index in range(1, TOTAL_USERS + 1):
        path = paths[index]
        user_id = f"U{index:05d}"
        day = 1 + (index * 3) % 30
        minute_base = 480 + (index * 7) % 540
        stamps: list[str] = []
        for pos, channel in enumerate(path):
            serial += 1
            minutes = minute_base + pos * 47
            hour = minutes // 60
            stamp = f"{PERIOD}-{day:02d}T{hour:02d}:{minutes % 60:02d}:00"
            stamps.append(stamp)
            channel_counter[channel] += 1
            touchpoints.append(
                {
                    "user_id": user_id,
                    "channel_code": channel,
                    "touched_at": stamp,
                    "cost": 0.0,
                    "campaign": CAMPAIGNS[channel][(index + pos) % len(CAMPAIGNS[channel])],
                    "seed_key": f"tp-{serial:06d}",
                }
            )
        if index in converted_users:
            amount = round(760 + (rng.below(1840) / 10.0) * 10, 2)
            conversions.append(
                {
                    "user_id": user_id,
                    "amount": amount,
                    "converted_at": stamps[-1],
                    "order_no": f"QY{PERIOD.replace('-', '')}{index:05d}",
                    "seed_key": f"cv-{index:05d}",
                }
            )

    # 触点成本按渠道月度成本均摊，尾差补到最后一条，保证合计=monthly_cost
    for channel in CHANNELS:
        rows = [row for row in touchpoints if row["channel_code"] == channel["code"]]
        if not rows:
            continue
        unit = round(channel["monthly_cost"] / len(rows), 2)
        for row in rows:
            row["cost"] = unit
        residual = round(channel["monthly_cost"] - unit * len(rows), 2)
        rows[-1]["cost"] = round(rows[-1]["cost"] + residual, 2)

    return {
        "channels": CHANNELS,
        "touchpoints": touchpoints,
        "conversions": conversions,
        "users": TOTAL_USERS,
        "converted_users": len(conversions),
        "period": PERIOD,
        "touchpoint_total": len(touchpoints),
        "channel_touchpoints": dict(sorted(channel_counter.items())),
        "revenue": round(sum(row["amount"] for row in conversions), 2),
    }


def expected_summary() -> str:
    return (
        f"SEED_SUMMARY brand={BRAND} users=3 sources={len(CHANNELS)} runs=1 "
        f"findings={len(CHANNELS)} pending={len(CHANNELS)}"
    )
