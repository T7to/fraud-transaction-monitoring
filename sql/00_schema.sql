CREATE TABLE IF NOT EXISTS transactions_raw (
    txn_id BIGSERIAL PRIMARY KEY,
    step INTEGER,
    type TEXT,
    amount NUMERIC(18, 2),
    nameorig TEXT,
    oldbalanceorg NUMERIC(18, 2),
    newbalanceorig NUMERIC(18, 2),
    namedest TEXT,
    oldbalancedest NUMERIC(18, 2),
    newbalancedest NUMERIC(18, 2),
    isfraud SMALLINT,
    isflaggedfraud SMALLINT
);

-- one row per pipeline run
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    status      TEXT,
    notes       TEXT
);

-- data quality results, one row per check per run
CREATE TABLE IF NOT EXISTS dq_results (
    run_id       TEXT NOT NULL,
    check_name   TEXT NOT NULL,
    severity     TEXT NOT NULL,
    failed_rows  BIGINT NOT NULL,
    total_rows   BIGINT NOT NULL,
    failed_pct   NUMERIC(7, 4),
    status       TEXT NOT NULL,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, check_name)
);

-- every alert any rule raised
CREATE TABLE IF NOT EXISTS alerts (
    run_id    TEXT    NOT NULL,
    rule_id   TEXT    NOT NULL,
    txn_id    BIGINT  NOT NULL,
    step      INTEGER NOT NULL,
    day       INTEGER NOT NULL,
    amount    NUMERIC(18, 2),
    isfraud   SMALLINT,
    PRIMARY KEY (run_id, rule_id, txn_id)
);

-- how each rule did, per period
CREATE TABLE IF NOT EXISTS rule_performance (
    run_id          TEXT    NOT NULL,
    rule_id         TEXT    NOT NULL,
    period          TEXT    NOT NULL,
    alerts          BIGINT  NOT NULL,
    true_positives  BIGINT  NOT NULL,
    total_fraud     BIGINT  NOT NULL,
    precision       NUMERIC(7, 4),
    recall          NUMERIC(7, 4),
    alerts_per_day  NUMERIC(12, 2),
    PRIMARY KEY (run_id, rule_id, period)
);

-- control results
CREATE TABLE IF NOT EXISTS control_log (
    run_id      TEXT NOT NULL,
    control_id  TEXT NOT NULL,
    status      TEXT NOT NULL,
    expected    TEXT,
    actual      TEXT,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, control_id)
);
