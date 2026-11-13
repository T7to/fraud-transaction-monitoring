-- Rule performance for one run, on two periods:
--   ALL  = every day in the data
--   TEST = the test period only (same days the model is judged on in Phase 5)
-- ANY_RULE = a transaction flagged by at least one rule R01-R05 (legacy flag excluded).

DELETE FROM rule_performance WHERE run_id = %(run_id)s;

INSERT INTO rule_performance
    (run_id, rule_id, period, alerts, true_positives, total_fraud,
     precision, recall, alerts_per_day)
WITH periods AS (
    SELECT 'ALL' AS period, 1 AS start_step
    UNION ALL
    SELECT 'TEST', %(test_start_step)s
),

-- Total fraud and number of days in each period (the denominators).
period_totals AS (
    SELECT p.period,
           SUM(t.isfraud)        AS total_fraud,
           COUNT(DISTINCT t.day) AS n_days
    FROM periods p
    JOIN transactions_clean t ON t.step >= p.start_step
    GROUP BY p.period
),

-- Every rule's alerts, plus ANY_RULE (each transaction counted once).
run_alerts AS (
    SELECT rule_id, txn_id, step, isfraud
    FROM alerts
    WHERE run_id = %(run_id)s AND rule_id <> 'ML_SCORE'
    UNION ALL
    SELECT DISTINCT 'ANY_RULE', txn_id, step, isfraud
    FROM alerts
    WHERE run_id = %(run_id)s AND rule_id NOT IN ('LEGACY_FLAG', 'ML_SCORE')
),

-- Alerts and true positives per rule and period.
rule_counts AS (
    SELECT a.rule_id, p.period,
           COUNT(*)       AS alerts,
           SUM(a.isfraud) AS true_positives
    FROM run_alerts a
    JOIN periods p ON a.step >= p.start_step
    GROUP BY a.rule_id, p.period
)

SELECT %(run_id)s,
       r.rule_id,
       r.period,
       r.alerts,
       r.true_positives,
       pt.total_fraud,
       ROUND(r.true_positives::NUMERIC / r.alerts, 4)                 AS precision,
       ROUND(r.true_positives::NUMERIC / NULLIF(pt.total_fraud, 0), 4) AS recall,
       ROUND(r.alerts::NUMERIC / pt.n_days, 2)                         AS alerts_per_day
FROM rule_counts r
JOIN period_totals pt ON pt.period = r.period;
