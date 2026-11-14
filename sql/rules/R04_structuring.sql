-- R04 structuring / smurfing
-- 3+ payments to the same account within 24h, each just under the threshold.
-- flags every payment that's part of the pattern

-- payments just below the threshold
WITH candidates AS (
    SELECT txn_id, step, day, amount, isfraud, namedest
    FROM transactions_clean
    WHERE amount >= %(threshold)s * (1 - %(band)s)
      AND amount <  %(threshold)s
),

-- how many of those went to the same account in the 24h up to each one
windows AS (
    SELECT namedest,
           step AS end_step,
           COUNT(*) OVER (PARTITION BY namedest ORDER BY step
                          RANGE BETWEEN 23 PRECEDING AND CURRENT ROW) AS n_in_window
    FROM candidates
)

SELECT DISTINCT c.txn_id, c.step, c.day, c.amount, c.isfraud
FROM candidates c
JOIN windows w
  ON w.namedest = c.namedest
 AND c.step BETWEEN w.end_step - 23 AND w.end_step
WHERE w.n_in_window >= %(min_count)s;
