-- the list investigators would work through: who got drained and where the money went
SELECT
    a.day,
    a.rule_id,
    t.txn_id,
    t.type,
    t.amount,
    t.nameorig       AS victim_account,
    t.oldbalanceorg  AS sender_before,
    t.newbalanceorig AS sender_after,
    t.namedest       AS suspected_mule,
    t.oldbalancedest AS receiver_before,
    t.newbalancedest AS receiver_after,
    t.isfraud        -- only known because PaySim is labelled, a real queue wouldn't have this
FROM alerts a
JOIN transactions_clean t USING (txn_id)
WHERE a.run_id = %(run_id)s
  AND a.rule_id = ANY(%(rules)s)
ORDER BY a.day, t.amount DESC
