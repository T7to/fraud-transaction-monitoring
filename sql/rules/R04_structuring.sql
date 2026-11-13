-- R04 Structuring (smurfing):
-- several transactions to the same destination within 24 hours, each just
-- below a reporting threshold. Alerts every transaction in the pattern.

-- 1. Candidates: amounts just below the threshold (between threshold * (1 - band) and threshold).
WITH candidates AS (
    SELECT txn_id, step, day, amount, isfraud, namedest
    FROM transactions_clean
    WHERE amount >= %(threshold)s * (1 - %(band)s)
      AND amount <  %(threshold)s
),

-- 2. For each candidate, count candidates to the same destination in the 24 hours ending at it.
windows AS (
    SELECT namedest,
           step AS end_step,
           COUNT(*) OVER (PARTITION BY namedest ORDER BY step
                          RANGE BETWEEN 23 PRECEDING AND CURRENT ROW) AS n_in_window
    FROM candidates
)

-- 3. Alert every candidate that falls inside a window with enough transactions.
SELECT DISTINCT c.txn_id, c.step, c.day, c.amount, c.isfraud
FROM candidates c
JOIN windows w
  ON w.namedest = c.namedest
 AND c.step BETWEEN w.end_step - 23 AND w.end_step
WHERE w.n_in_window >= %(min_count)s;
