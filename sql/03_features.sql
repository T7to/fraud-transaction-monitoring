DROP TABLE IF EXISTS features;

CREATE TABLE features AS
SELECT
    t.txn_id,
    t.step,
    t.day,
    t.isfraud,

    -- about the transaction itself
    (t.type = 'TRANSFER')::INT                              AS is_transfer,
    ln(1 + t.amount)                                        AS log_amount,
    t.amount / NULLIF(t.oldbalanceorg, 0)                   AS pct_balance_moved,
    (t.oldbalanceorg = 0)::INT                              AS orig_zero_balance_before,
    (t.oldbalanceorg > 0 AND t.newbalanceorig = 0)::INT     AS orig_drained,
    t.newbalanceorig + t.amount - t.oldbalanceorg           AS error_balance_orig,
    t.oldbalancedest + t.amount - t.newbalancedest          AS error_balance_dest,
    (t.oldbalancedest = 0 AND t.newbalancedest = 0)::INT    AS dest_balance_unchanged,

    -- the receiving account's history
    COUNT(*) OVER w24                                       AS dest_prior_txn_24h,
    COALESCE(SUM(t.amount) OVER w24, 0)                     AS dest_prior_amount_24h,
    COUNT(*) OVER wall                                      AS dest_prior_txn_all,
    AVG(t.amount) OVER wall                                 AS dest_prior_avg_amount,
    COALESCE(t.step - MAX(t.step) OVER wall, -1)            AS hours_since_dest_last_txn,
    (COUNT(*) OVER wall = 0)::INT                           AS dest_first_seen,
    t.amount / NULLIF(AVG(t.amount) OVER wall, 0)           AS amount_vs_dest_avg

FROM transactions_clean t
WINDOW
    w24  AS (PARTITION BY t.namedest ORDER BY t.step
             RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING),
    wall AS (PARTITION BY t.namedest ORDER BY t.step
             RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);

ALTER TABLE features ADD PRIMARY KEY (txn_id);
ANALYZE features;

-- per account per day, for R03.
-- needs COUNT(DISTINCT) which doesn't work in window functions.
-- covers the whole day (incl. later txns) so only use it in end-of-day rules, NOT the model

DROP TABLE IF EXISTS dest_daily;

CREATE TABLE dest_daily AS
SELECT
    namedest,
    day,
    COUNT(*)                 AS txn_count,
    COUNT(DISTINCT nameorig) AS distinct_senders,
    SUM(amount)              AS total_amount
FROM transactions_clean
GROUP BY namedest, day;

ALTER TABLE dest_daily ADD PRIMARY KEY (namedest, day);
ANALYZE dest_daily;