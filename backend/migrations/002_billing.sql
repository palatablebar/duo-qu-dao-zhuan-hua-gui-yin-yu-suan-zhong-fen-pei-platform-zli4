-- 002_billing.sql：账单批次 / 台账分录 / 预算调整（人类可读 DDL 参考，运行时不执行；
-- 新表由 SQLAlchemy create_all 自动建；已有库只需手动执行下面的 ALTER TABLE 加列）

ALTER TABLE channels ADD COLUMN held_amount DOUBLE NOT NULL DEFAULT 0;

CREATE TABLE bill_batches (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    batch_no        VARCHAR(48)  NOT NULL UNIQUE,
    period          VARCHAR(10)  NOT NULL,
    kind            VARCHAR(16)  NOT NULL DEFAULT 'entry',
    status          VARCHAR(16)  NOT NULL DEFAULT 'posted',
    row_count       INT          NOT NULL DEFAULT 0,
    spend_total     DOUBLE       NOT NULL DEFAULT 0,
    refund_total    DOUBLE       NOT NULL DEFAULT 0,
    net_total       DOUBLE       NOT NULL DEFAULT 0,
    error           TEXT,
    payload_hash    VARCHAR(64)  NOT NULL DEFAULT '',
    created_by      VARCHAR(160) NOT NULL,
    created_at      DATETIME     NOT NULL,
    INDEX ix_bill_batches_period (period),
    INDEX ix_bill_batches_status (status)
);

CREATE TABLE bill_entries (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    entry_no        VARCHAR(64)  NOT NULL UNIQUE,
    batch_id        INT          NOT NULL,
    channel_id      INT          NOT NULL,
    kind            VARCHAR(16)  NOT NULL,
    amount          DOUBLE       NOT NULL DEFAULT 0,
    reverses_id     INT          UNIQUE,
    memo            VARCHAR(200),
    row_no          INT          NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL,
    UNIQUE KEY uq_bill_entries_batch_row (batch_id, row_no),
    INDEX ix_bill_entries_channel (channel_id),
    CONSTRAINT fk_bill_entries_batch FOREIGN KEY (batch_id) REFERENCES bill_batches(id) ON DELETE CASCADE,
    CONSTRAINT fk_bill_entries_channel FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    CONSTRAINT fk_bill_entries_reverses FOREIGN KEY (reverses_id) REFERENCES bill_entries(id)
);

CREATE TABLE budget_adjustments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    adjust_no       VARCHAR(48)  NOT NULL UNIQUE,
    channel_id      INT          NOT NULL,
    delta           DOUBLE       NOT NULL DEFAULT 0,
    hold_amount     DOUBLE       NOT NULL DEFAULT 0,
    reason          VARCHAR(200) NOT NULL DEFAULT '',
    status          VARCHAR(16)  NOT NULL DEFAULT 'held',
    request_key     VARCHAR(64)  NOT NULL UNIQUE,
    created_by      VARCHAR(160) NOT NULL,
    created_at      DATETIME     NOT NULL,
    decided_by      VARCHAR(160),
    decided_at      DATETIME,
    INDEX ix_budget_adjustments_status (status),
    CONSTRAINT fk_budget_adjustments_channel FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);
