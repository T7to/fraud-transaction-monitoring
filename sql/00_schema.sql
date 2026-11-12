DROP TABLE IF EXISTS transactions_raw;

CREATE TABLE transactions_raw (
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
