-- mixcredit 核心表结构参考（MySQL 8.0 语法；运行时不执行，建表由 SQLAlchemy create_all 完成）

CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      DATETIME     NOT NULL
);

CREATE TABLE channels (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(80)  NOT NULL,
    type            VARCHAR(20)  NOT NULL,
    monthly_cost    DOUBLE       NOT NULL DEFAULT 0,
    budget          DOUBLE       NOT NULL DEFAULT 0,
    owner           VARCHAR(80),
    note            TEXT,
    enabled         TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL
);

CREATE TABLE touchpoints (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(16)  NOT NULL,
    channel_id      INT          NOT NULL,
    touched_at      DATETIME     NOT NULL,
    cost            DOUBLE       NOT NULL DEFAULT 0,
    campaign        VARCHAR(60),
    seed_key        VARCHAR(40)  UNIQUE,
    created_at      DATETIME     NOT NULL,
    INDEX ix_touchpoints_user (user_id),
    INDEX ix_touchpoints_channel (channel_id),
    INDEX ix_touchpoints_time (touched_at),
    CONSTRAINT fk_touchpoints_channel FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

CREATE TABLE conversions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(16)  NOT NULL,
    amount          DOUBLE       NOT NULL DEFAULT 0,
    converted_at    DATETIME     NOT NULL,
    order_no        VARCHAR(40)  NOT NULL UNIQUE,
    seed_key        VARCHAR(40)  UNIQUE,
    created_at      DATETIME     NOT NULL,
    INDEX ix_conversions_user (user_id)
);

CREATE TABLE attribution_runs (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    run_no             VARCHAR(40)  NOT NULL UNIQUE,
    period             VARCHAR(10)  NOT NULL,
    model              VARCHAR(24)  NOT NULL,
    trigger            VARCHAR(20)  NOT NULL,
    status             VARCHAR(16)  NOT NULL,
    operator_email     VARCHAR(160) NOT NULL,
    users_count        INT          NOT NULL DEFAULT 0,
    touchpoints_count  INT          NOT NULL DEFAULT 0,
    conversions_count  INT          NOT NULL DEFAULT 0,
    revenue            DOUBLE       NOT NULL DEFAULT 0,
    metrics            JSON,
    log_text           TEXT,
    seed_key           VARCHAR(120) UNIQUE,
    started_at         DATETIME     NOT NULL,
    finished_at        DATETIME
);

CREATE TABLE attributions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    run_id            INT          NOT NULL,
    channel_id        INT          NOT NULL,
    credit_amount     DOUBLE       NOT NULL DEFAULT 0,
    share             DOUBLE       NOT NULL DEFAULT 0,
    markov_share      DOUBLE       NOT NULL DEFAULT 0,
    last_click_share  DOUBLE       NOT NULL DEFAULT 0,
    shapley_share     DOUBLE       NOT NULL DEFAULT 0,
    removal_effect    DOUBLE       NOT NULL DEFAULT 0,
    roi               DOUBLE       NOT NULL DEFAULT 0,
    cost              DOUBLE       NOT NULL DEFAULT 0,
    budget            DOUBLE       NOT NULL DEFAULT 0,
    suggested_budget  DOUBLE       NOT NULL DEFAULT 0,
    delta_pct         DOUBLE       NOT NULL DEFAULT 0,
    status            VARCHAR(16)  NOT NULL DEFAULT 'pending',
    reviewer          VARCHAR(160),
    review_note       TEXT,
    payload           JSON,
    created_at        DATETIME     NOT NULL,
    updated_at        DATETIME     NOT NULL,
    UNIQUE KEY uq_attributions_run_channel (run_id, channel_id),
    CONSTRAINT fk_attributions_run FOREIGN KEY (run_id) REFERENCES attribution_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_attributions_channel FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
);

CREATE TABLE audit_logs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      DATETIME     NOT NULL
);
