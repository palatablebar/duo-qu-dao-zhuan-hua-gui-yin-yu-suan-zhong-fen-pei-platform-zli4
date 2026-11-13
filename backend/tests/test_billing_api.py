"""账单 API 集成测试：TestClient + SQLite 依赖覆盖。

中间件说明：审计中间件写库失败会静默降级、限流中间件在 Redis 不可用时降级，
因此可以用 SQLite 跑完整 HTTP 链路，验证 401/403/409/422/201 与导出一致性。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.app import create_app
from src.config.database import get_db
from src.models import Base
from src.models.channel import Channel
from src.utils.security import create_access_token


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add_all(
        [
            Channel(code="search", name="品牌搜索", type="search", monthly_cost=0, budget=100000, enabled=True),
            Channel(code="feed", name="效果信息流", type="feed", monthly_cost=0, budget=50000, enabled=True),
        ]
    )
    session.commit()

    app = create_app()

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)
    test_client.db_session = session
    yield test_client
    session.close()


def token(role: str) -> dict:
    jwt_token, _ = create_access_token(f"{role}@mixcredit.io", role)
    return {"Authorization": f"Bearer {jwt_token}"}


def admin_headers():
    return token("admin")


def analyst_headers():
    return token("analyst")


def viewer_headers():
    return token("viewer")


def batch_payload(batch_no="B-API-1", rows=None):
    return {
        "batch_no": batch_no,
        "period": "2026-11",
        "rows": rows or [{"channel_code": "search", "kind": "spend", "amount": 1000, "memo": None}],
    }


# ---------- 权限 ----------

def test_auth_required(client):
    assert client.get("/api/billing/overview").status_code == 401
    assert client.post("/api/billing/batches", json=batch_payload()).status_code == 401


def test_viewer_and_analyst_cannot_write(client):
    assert client.get("/api/billing/overview", headers=viewer_headers()).status_code == 403
    assert client.get("/api/billing/overview", headers=analyst_headers()).status_code == 200
    response = client.post("/api/billing/batches", json=batch_payload(), headers=analyst_headers())
    assert response.status_code == 403
    response = client.post("/api/billing/adjustments", json=adjust_payload(client), headers=analyst_headers())
    assert response.status_code == 403


def adjust_payload(client, delta=-60000, key="req-api-1"):
    channel_id = client.db_session.query(Channel).filter_by(code="search").one().id
    return {"channel_id": channel_id, "delta": delta, "reason": "月度预算重排", "request_key": key}


# ---------- 批次：整批成功或整批失败 ----------

def test_batch_all_or_nothing_via_api(client):
    payload = batch_payload(
        "B-API-FAIL",
        [
            {"channel_code": "search", "kind": "spend", "amount": 1000, "memo": "合法行"},
            {"channel_code": "ghost", "kind": "spend", "amount": 500, "memo": "坏行"},
        ],
    )
    response = client.post("/api/billing/batches", json=payload, headers=admin_headers())
    assert response.status_code == 422
    assert response.json()["code"] == "BATCH_FAILED"
    assert "第2行" in response.json()["detail"]["error"]
    # 前面的合法行也没有写入
    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    assert overview["totals"]["net_spend"] == 0
    # 失败批次留痕可查
    batches = client.get("/api/billing/batches", headers=admin_headers()).json()
    assert batches["total"] == 1
    assert batches["items"][0]["status"] == "failed"
    assert batches["items"][0]["error"]


def test_batch_post_and_idempotent_replay(client):
    payload = batch_payload(
        "B-API-OK",
        [
            {"channel_code": "search", "kind": "spend", "amount": 30000, "memo": None},
            {"channel_code": "search", "kind": "refund", "amount": 5000, "memo": "退单"},
        ],
    )
    first = client.post("/api/billing/batches", json=payload, headers=admin_headers())
    assert first.status_code == 201
    body = first.json()
    assert body["status"] == "posted"
    assert body["net_total"] == 25000
    assert len(body["entries"]) == 2

    replay = client.post("/api/billing/batches", json=payload, headers=admin_headers())
    assert replay.status_code == 201
    assert replay.json()["id"] == body["id"]

    conflict = client.post(
        "/api/billing/batches",
        json=batch_payload("B-API-OK", [{"channel_code": "search", "kind": "spend", "amount": 1, "memo": None}]),
        headers=admin_headers(),
    )
    assert conflict.status_code == 409

    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    search = next(item for item in overview["items"] if item["code"] == "search")
    assert search["net_spend"] == 25000
    assert search["available"] == 75000


def test_batch_validation_422(client):
    bad = batch_payload("B-API-VAL", [{"channel_code": "search", "kind": "spend", "amount": -5, "memo": None}])
    assert client.post("/api/billing/batches", json=bad, headers=admin_headers()).status_code == 422
    bad_period = batch_payload("B-API-VAL2")
    bad_period["period"] = "2026-13"
    assert client.post("/api/billing/batches", json=bad_period, headers=admin_headers()).status_code == 422


# ---------- 冲正 ----------

def test_reverse_via_api(client):
    client.post("/api/billing/batches", json=batch_payload("B-API-REV"), headers=admin_headers())
    entries = client.get("/api/billing/entries", headers=admin_headers()).json()["items"]
    entry_id = entries[0]["id"]

    reversed_batch = client.post(f"/api/billing/entries/{entry_id}/reverse", headers=admin_headers())
    assert reversed_batch.status_code == 201
    assert reversed_batch.json()["kind"] == "reversal"

    again = client.post(f"/api/billing/entries/{entry_id}/reverse", headers=admin_headers())
    assert again.status_code == 409

    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    assert overview["totals"]["net_spend"] == 0


# ---------- 预算调整：先占用再批准 ----------

def test_adjustment_hold_approve_flow(client):
    created = client.post("/api/billing/adjustments", json=adjust_payload(client), headers=admin_headers())
    assert created.status_code == 201
    adjustment = created.json()
    assert adjustment["status"] == "held"
    assert adjustment["hold_amount"] == 60000

    # 同一笔余额不能被第二次占用
    second = client.post("/api/billing/adjustments", json=adjust_payload(client, key="req-api-2"), headers=admin_headers())
    assert second.status_code == 409
    assert second.json()["code"] == "INSUFFICIENT_BALANCE"

    # 幂等重放：同 request_key 返回原单
    replay = client.post("/api/billing/adjustments", json=adjust_payload(client), headers=admin_headers())
    assert replay.status_code == 201
    assert replay.json()["id"] == adjustment["id"]

    approved = client.post(f"/api/billing/adjustments/{adjustment['id']}/approve", headers=admin_headers())
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    again = client.post(f"/api/billing/adjustments/{adjustment['id']}/approve", headers=admin_headers())
    assert again.status_code == 409

    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    search = next(item for item in overview["items"] if item["code"] == "search")
    assert search["budget"] == 40000
    assert search["held"] == 0


def test_adjustment_reject_releases_hold(client):
    created = client.post("/api/billing/adjustments", json=adjust_payload(client, key="req-api-9"), headers=admin_headers())
    adjustment_id = created.json()["id"]
    rejected = client.post(f"/api/billing/adjustments/{adjustment_id}/reject", headers=admin_headers())
    assert rejected.status_code == 200
    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    assert overview["totals"]["held"] == 0
    assert overview["totals"]["budget"] == 150000


# ---------- 导出与页面一致 ----------

def test_export_matches_overview(client):
    client.post(
        "/api/billing/batches",
        json=batch_payload("B-API-EXP", [{"channel_code": "search", "kind": "spend", "amount": 30000, "memo": None}]),
        headers=admin_headers(),
    )
    client.post("/api/billing/adjustments", json=adjust_payload(client, delta=-20000, key="req-api-exp"), headers=admin_headers())

    overview = client.get("/api/billing/overview", headers=admin_headers()).json()
    csv_response = client.get("/api/exports/balances.csv", headers=admin_headers())
    assert csv_response.status_code == 200
    text = csv_response.content.decode("utf-8-sig")
    for item in overview["items"]:
        assert item["code"] in text
        assert f"{item['available']:.2f}" in text
        assert f"{item['held']:.2f}" in text
    assert f"{overview['totals']['available']:.2f}" in text

    # viewer 不能导出
    assert client.get("/api/exports/balances.csv", headers=viewer_headers()).status_code == 403
    # 台账导出
    entries_csv = client.get("/api/exports/bill-entries.csv", headers=admin_headers())
    assert entries_csv.status_code == 200
    assert "B-API-EXP" in entries_csv.content.decode("utf-8-sig")
