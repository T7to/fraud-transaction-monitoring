-- Raw transactions: untouched copy of the source file.
-- IF NOT EXISTS keeps this file safe to rerun; load.py truncates before each load.
CREATE TABLE IF NOT EXISTS transactions_raw (
    txn_id BIGSERIAL PRIMARY KEY,
    step INTEGER,
    type TEXT,
    amount NUMERIC(18, 2), --18 digits with 2 after decimal point
    nameorig TEXT,
    oldbalanceorg NUMERIC(18, 2),
    newbalanceorig NUMERIC(18, 2),
    namedest TEXT,
    oldbalancedest NUMERIC(18, 2),
    newbalancedest NUMERIC(18, 2),
    isfraud SMALLINT,
    isflaggedfraud SMALLINT
);

-- Pipeline run register: one row per run, for audit trail.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    status      TEXT,
    notes       TEXT
);

-- Data quality results: one row per check per run.
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

-- Alerts raised by rules and the model: one row per (run, rule, transaction).
CREATE TABLE IF NOT EXISTS alerts (
    run_id    TEXT    NOT NULL,
    rule_id   TEXT    NOT NULL,
    txn_id    BIGINT  NOT NULL,
    step      INTEGER NOT NULL,
    day       INTEGER NOT NULL,
    amount    NUMERIC(18, 2),
    isfraud   SMALLINT,
    score     NUMERIC(10, 6),
    PRIMARY KEY (run_id, rule_id, txn_id)
);

-- Performance of each rule per evaluation period.
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
