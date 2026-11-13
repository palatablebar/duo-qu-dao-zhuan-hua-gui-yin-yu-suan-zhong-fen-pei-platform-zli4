"""账单批次 / 冲正 / 预算占用 的服务层测试（SQLite）。

覆盖四条事务口径：
1. 批次整批成功或整批失败（一行错，前面的行也不落库）；
2. 台账只追加，冲正生成 reversal 分录，历史分录不被修改；
3. 预算调整先占用再批准，两名经理同时提交不能占用同一笔余额；
4. 余额导出与页面（channel_balances）数字一致。
"""
from __future__ import annotations

import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base
from src.models.billing import BillBatch, BillEntry, BudgetAdjustment
from src.models.channel import Channel
from src.services import billing_service
from src.services.export_service import balances_csv
from src.utils.errors import AppError

OPERATOR = "manager@mixcredit.io"


def make_session_factory(url: str = "sqlite://", **connect_args):
    if url == "sqlite://":
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)  # expire_on_commit=True：提交后读取必然回库


@pytest.fixture()
def db():
    factory = make_session_factory()
    session = factory()
    session.add_all(
        [
            Channel(code="search", name="品牌搜索", type="search", monthly_cost=0, budget=100000, enabled=True),
            Channel(code="feed", name="效果信息流", type="feed", monthly_cost=0, budget=50000, enabled=True),
        ]
    )
    session.commit()
    yield session
    session.close()


def bill_rows(*rows):
    return [
        {"channel_code": code, "kind": kind, "amount": amount, "memo": memo}
        for code, kind, amount, memo in rows
    ]


def post(db, batch_no="B-1", rows=None, period="2026-11"):
    payload = {"batch_no": batch_no, "period": period, "rows": rows or bill_rows(("search", "spend", 1000.0, None))}
    batch, created = billing_service.submit_batch(db, payload, OPERATOR)
    db.commit()
    return batch, created


def adjust(db, channel_id, delta, key):
    adjustment, created = billing_service.create_adjustment(
        db, {"channel_id": channel_id, "delta": delta, "reason": "月度预算重排", "request_key": key}, OPERATOR
    )
    db.commit()
    return adjustment, created


def channel_of(db, code="search"):
    return db.scalar(select(Channel).where(Channel.code == code))


def balance_of(db, code="search"):
    data = billing_service.channel_balances(db)
    return next(item for item in data["items"] if item["code"] == code)


# ---------- 1. 整批成功或整批失败 ----------

def test_batch_all_or_nothing(db):
    rows = bill_rows(
        ("search", "spend", 1000.0, "第一行合法"),
        ("ghost", "spend", 500.0, "渠道不存在"),
    )
    batch, created = post(db, "B-FAIL", rows)
    assert created is True
    assert batch.status == "failed"
    assert "第2行" in batch.error
    # 第一行合法也没有写入：分录为零，只有一条 failed 批次记录
    assert db.scalar(select(func.count()).select_from(BillEntry)) == 0
    assert db.scalar(select(func.count()).select_from(BillBatch)) == 1
    assert balance_of(db)["net_spend"] == 0


def test_batch_success_writes_all_rows(db):
    rows = bill_rows(
        ("search", "spend", 1000.0, None),
        ("search", "refund", 200.0, "退单"),
        ("feed", "spend", 300.0, None),
    )
    batch, _ = post(db, "B-OK", rows)
    assert batch.status == "posted"
    assert batch.spend_total == 1300.0
    assert batch.refund_total == 200.0
    assert batch.net_total == 1100.0
    assert db.scalar(select(func.count()).select_from(BillEntry)) == 3
    assert balance_of(db)["net_spend"] == 800.0
    assert balance_of(db)["available"] == 100000 - 800


def test_batch_idempotent_replay(db):
    rows = bill_rows(("search", "spend", 1000.0, None))
    first, created_first = post(db, "B-SAME", rows)
    second, created_second = post(db, "B-SAME", rows)
    assert created_first is True and created_second is False
    assert second.id == first.id
    assert db.scalar(select(func.count()).select_from(BillEntry)) == 1


def test_batch_same_number_different_content_conflict(db):
    post(db, "B-DUP", bill_rows(("search", "spend", 1000.0, None)))
    with pytest.raises(AppError) as exc:
        post(db, "B-DUP", bill_rows(("search", "spend", 2000.0, None)))
    assert exc.value.status_code == 409


# ---------- 2. 只追加冲正 ----------

def test_reversal_is_append_only(db):
    post(db, "B-REV", bill_rows(("search", "spend", 1000.0, None)))
    entry = db.scalar(select(BillEntry))
    reversal_batch = billing_service.reverse_entry(db, entry.id, OPERATOR)
    db.commit()

    reversal = db.scalar(select(BillEntry).where(BillEntry.reverses_id == entry.id))
    assert reversal_batch.kind == "reversal"
    assert reversal.kind == "reversal"
    assert reversal.amount == -1000.0
    # 原分录未被修改、未被删除
    assert entry.amount == 1000.0
    assert db.scalar(select(func.count()).select_from(BillEntry)) == 2
    # 净消耗归零，可用余额恢复
    assert balance_of(db)["net_spend"] == 0
    assert balance_of(db)["available"] == 100000


def test_reversal_only_once(db):
    post(db, "B-REV2", bill_rows(("search", "spend", 1000.0, None)))
    entry = db.scalar(select(BillEntry))
    billing_service.reverse_entry(db, entry.id, OPERATOR)
    db.commit()
    with pytest.raises(AppError) as exc:
        billing_service.reverse_entry(db, entry.id, OPERATOR)
    assert exc.value.status_code == 409


def test_reversal_entry_cannot_be_reversed(db):
    post(db, "B-REV3", bill_rows(("search", "spend", 1000.0, None)))
    entry = db.scalar(select(BillEntry))
    billing_service.reverse_entry(db, entry.id, OPERATOR)
    db.commit()
    reversal = db.scalar(select(BillEntry).where(BillEntry.kind == "reversal"))
    with pytest.raises(AppError) as exc:
        billing_service.reverse_entry(db, reversal.id, OPERATOR)
    assert exc.value.status_code == 422


# ---------- 3. 先占用再批准 + 并发不占同一笔余额 ----------

def test_reserve_then_approve_applies_budget(db):
    channel = channel_of(db)
    adjustment, _ = adjust(db, channel.id, -40000, "k-1")
    assert adjustment.status == "held"
    balance = balance_of(db)
    assert balance["held"] == 40000
    assert balance["available"] == 60000

    billing_service.decide_adjustment(db, adjustment.id, approve=True, decided_by="boss@mixcredit.io")
    db.commit()
    balance = balance_of(db)
    assert balance["budget"] == 60000
    assert balance["held"] == 0
    assert balance["available"] == 60000


def test_reserve_beyond_available_rejected(db):
    channel = channel_of(db)
    adjust(db, channel.id, -40000, "k-1")
    with pytest.raises(AppError) as exc:
        adjust(db, channel.id, -70000, "k-2")
    assert exc.value.code == "INSUFFICIENT_BALANCE"
    assert exc.value.status_code == 409
    # 第一笔占用不受影响
    assert balance_of(db)["held"] == 40000


def test_spend_reduces_room_for_reservation(db):
    post(db, "B-SPEND", bill_rows(("search", "spend", 30000.0, None)))
    channel = channel_of(db)
    with pytest.raises(AppError) as exc:
        adjust(db, channel.id, -80000, "k-3")
    assert exc.value.code == "INSUFFICIENT_BALANCE"
    adjustment, _ = adjust(db, channel.id, -70000, "k-4")
    assert adjustment.status == "held"
    assert balance_of(db)["available"] == 0


def test_reject_releases_hold(db):
    channel = channel_of(db)
    adjustment, _ = adjust(db, channel.id, -40000, "k-5")
    billing_service.decide_adjustment(db, adjustment.id, approve=False, decided_by="boss@mixcredit.io")
    db.commit()
    balance = balance_of(db)
    assert balance["held"] == 0
    assert balance["budget"] == 100000


def test_decide_twice_conflict(db):
    channel = channel_of(db)
    adjustment, _ = adjust(db, channel.id, -40000, "k-6")
    billing_service.decide_adjustment(db, adjustment.id, approve=True, decided_by="boss@mixcredit.io")
    db.commit()
    with pytest.raises(AppError) as exc:
        billing_service.decide_adjustment(db, adjustment.id, approve=False, decided_by="boss@mixcredit.io")
    assert exc.value.status_code == 409


def test_adjustment_request_key_idempotent(db):
    channel = channel_of(db)
    first, created_first = adjust(db, channel.id, -40000, "k-same")
    second, created_second = adjust(db, channel.id, -40000, "k-same")
    assert created_first is True and created_second is False
    assert second.id == first.id
    # 重试不会重复占用
    assert balance_of(db)["held"] == 40000
    assert db.scalar(select(func.count()).select_from(BudgetAdjustment)) == 1


def test_concurrent_managers_cannot_reserve_same_balance(tmp_path):
    """两名经理同时提交：预算 10 万各占用 6 万，恰好一人成功。"""
    db_file = tmp_path / "race.db"
    factory = make_session_factory(f"sqlite:///{db_file}", check_same_thread=False, timeout=30)
    with factory() as session:
        session.add(Channel(code="search", name="品牌搜索", type="search", monthly_cost=0, budget=100000, enabled=True))
        session.commit()
        channel_id = session.scalar(select(Channel.id))

    barrier = threading.Barrier(2)
    outcomes = []

    def manager(request_key):
        with factory() as session:
            barrier.wait()
            try:
                billing_service.create_adjustment(
                    session,
                    {"channel_id": channel_id, "delta": -60000, "reason": "抢同一笔余额", "request_key": request_key},
                    "manager@mixcredit.io",
                )
                session.commit()
                outcomes.append("ok")
            except AppError as err:
                session.rollback()
                outcomes.append(err.code)

    threads = [threading.Thread(target=manager, args=(f"race-{idx}",)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["INSUFFICIENT_BALANCE", "ok"]
    with factory() as session:
        channel = session.get(Channel, channel_id)
        assert channel.held_amount == 60000
        assert session.scalar(select(func.count()).select_from(BudgetAdjustment)) == 1


# ---------- 4. 导出与页面一致 ----------

def test_export_matches_page(db):
    post(db, "B-EXP", bill_rows(("search", "spend", 30000.0, None), ("feed", "refund", 500.0, None)))
    channel = channel_of(db)
    adjust(db, channel.id, -20000, "k-exp")

    data = billing_service.channel_balances(db)
    csv_text = balances_csv(db).decode("utf-8-sig")
    for item in data["items"]:
        assert item["code"] in csv_text
        assert f"{item['available']:.2f}" in csv_text
        assert f"{item['held']:.2f}" in csv_text
    totals = data["totals"]
    assert f"{totals['available']:.2f}" in csv_text
    assert "合计" in csv_text
