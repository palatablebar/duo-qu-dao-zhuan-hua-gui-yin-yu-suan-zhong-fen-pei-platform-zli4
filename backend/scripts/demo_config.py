"""演示账号与组织常量（业务数据见 business_seed.py）。"""

DEMO_PASSWORD = "Demo@2026"
ORG = "清野日化 · 增长组"

DEMO_USERS = [
    ("admin@mixcredit.io", "林可 · 增长负责人", "admin"),
    ("analyst@mixcredit.io", "周棠 · 归因分析师", "analyst"),
    ("viewer@mixcredit.io", "陈默 · 渠道运营（只读）", "viewer"),
]

SEED_RUN_KEY = "seed-run-202610"
SEED_AUDIT = [
    ("seed-audit-1", "admin@mixcredit.io", "admin", "channel.update", "channel", {"code": "content", "budget": 180000}),
    ("seed-audit-2", "analyst@mixcredit.io", "analyst", "run.create", "attribution_run", {"period": "2026-10"}),
    ("seed-audit-3", "admin@mixcredit.io", "admin", "export.attributions", "attribution", {"rows": 5}),
]

# 财务合并的 10 月账单（5 条消耗 + 1 条退款），批次号即幂等键
SEED_BILL_BATCH_NO = "BILL-2026-10-SEED"
SEED_BILL_ROWS = [
    ("brand_search", "spend", 96500.0, "10月品牌词消耗"),
    ("feed", "spend", 188200.0, "10月信息流消耗"),
    ("content", "spend", 121300.0, "10月KOC种草消耗"),
    ("community", "spend", 42600.0, "10月社群运营消耗"),
    ("live", "spend", 132800.0, "10月直播消耗"),
    ("live", "refund", 8600.0, "直播退单退款"),
]

# 一笔在途占用的预算调整（request_key 幂等）
SEED_ADJUST_KEY = "seed-adjust-hold-1"
SEED_ADJUST_CHANNEL = "live"
SEED_ADJUST_DELTA = -20000.0
SEED_ADJUST_REASON = "直播退单率偏高，先占用 2 万，复核后挪回内容种草"
