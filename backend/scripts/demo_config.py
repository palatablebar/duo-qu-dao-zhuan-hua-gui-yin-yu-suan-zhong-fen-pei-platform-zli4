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
