WITH counts AS (
    SELECT
        COUNT(*) AS total_rows,
        COUNT(*) FILTER (WHERE num_nulls(step, type, amount, nameorig, oldbalanceorg,
            newbalanceorig, namedest, oldbalancedest, newbalancedest,
            isfraud, isflaggedfraud) > 0) AS null_key_columns,
        COUNT(*) FILTER (WHERE amount < 0) AS negative_amount,
        COUNT(*) FILTER (WHERE type <> ALL (%(valid_types)s)) AS unknown_type,
        COUNT(*) FILTER (WHERE isfraud NOT IN (0, 1)
                            OR isflaggedfraud NOT IN (0, 1)) AS invalid_label,
        COUNT(*) FILTER (WHERE step NOT BETWEEN %(min_step)s AND %(max_step)s) AS step_out_of_range,
        COUNT(*) FILTER (WHERE amount = 0) AS zero_amount,
        COUNT(*) FILTER (WHERE type <> 'CASH_IN'
            AND ABS(oldbalanceorg - amount - newbalanceorig) > %(balance_tolerance)s) AS sender_balance_mismatch,
        COUNT(*) FILTER (WHERE nameorig = namedest) AS self_transfer
    FROM transactions_raw
),
dups AS (
    SELECT COALESCE(SUM(n - 1), 0)::BIGINT AS duplicate_rows
    FROM (
        SELECT COUNT(*) AS n
        FROM transactions_raw
        GROUP BY step, type, amount, nameorig, oldbalanceorg, newbalanceorig,
                 namedest, oldbalancedest, newbalancedest, isfraud, isflaggedfraud
        HAVING COUNT(*) > 1
    ) d
)
SELECT v.check_name, v.severity, v.failed_rows, c.total_rows
FROM counts c
CROSS JOIN dups d
CROSS JOIN LATERAL (VALUES
    ('null_key_columns', 'CRITICAL', c.null_key_columns),
    ('negative_amount', 'CRITICAL', c.negative_amount),
    ('unknown_type', 'CRITICAL', c.unknown_type),
    ('invalid_label', 'CRITICAL', c.invalid_label),
    ('step_out_of_range', 'WARNING', c.step_out_of_range),
    ('duplicate_rows', 'WARNING', d.duplicate_rows),
    ('zero_amount', 'WARNING', c.zero_amount),
    ('sender_balance_mismatch', 'INFO', c.sender_balance_mismatch),
    ('self_transfer', 'INFO', c.self_transfer)
) AS v(check_name, severity, failed_rows)
ORDER BY CASE v.severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END,
         v.check_name;