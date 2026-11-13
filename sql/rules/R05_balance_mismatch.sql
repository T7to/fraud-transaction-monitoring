-- R05 Balance mismatch (system or control anomaly):
-- the sender's balance does not move by the transaction amount.
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE ABS(newbalanceorig + amount - oldbalanceorg) > %(tolerance)s
  AND amount >= %(min_amount)s;
