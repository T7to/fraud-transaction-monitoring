DELETE FROM rule_performance WHERE run_id = %(run_id)s;

INSERT INTO rule_performance
    (run_id, rule_id, period, alerts, true_positives, total_fraud,
     precision, recall, alerts_per_day)
WITH periods AS (
    SELECT 'ALL' AS period, 1 AS start_step
    UNION ALL
    SELECT 'TEST', %(test_start_step)s
),

-- total fraud + number of days per period
period_totals AS (
    SELECT p.period,
           SUM(t.isfraud)        AS total_fraud,
           COUNT(DISTINCT t.day) AS n_days
    FROM periods p
    JOIN transactions_clean t ON t.step >= p.start_step
    GROUP BY p.period
),

run_alerts AS (
    SELECT rule_id, txn_id, step, isfraud
    FROM alerts
    WHERE run_id = %(run_id)s
    UNION ALL
    -- distinct so a txn hit by 3 rules only counts once
    SELECT DISTINCT 'ANY_RULE', txn_id, step, isfraud
    FROM alerts
    WHERE run_id = %(run_id)s AND rule_id <> 'LEGACY_FLAG'
),

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
       ROUND(r.true_positives::NUMERIC / r.alerts, 4),
       ROUND(r.true_positives::NUMERIC / NULLIF(pt.total_fraud, 0), 4),
       ROUND(r.alerts::NUMERIC / pt.n_days, 2)
FROM rule_counts r
JOIN period_totals pt ON pt.period = r.period;
