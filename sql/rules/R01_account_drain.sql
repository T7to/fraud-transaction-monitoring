-- R01 Account drain (account takeover):
-- the sender moves almost all of their balance in one go.
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE oldbalanceorg > 0
  AND amount >= %(drain_ratio)s * oldbalanceorg
  AND amount >= %(min_amount)s;
