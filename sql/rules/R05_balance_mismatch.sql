-- R05 sender balance doesn't move by the amount sent
-- (more of a system/data issue than fraud, kept to show that)
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE ABS(newbalanceorig + amount - oldbalanceorg) > %(tolerance)s
  AND amount >= %(min_amount)s;
