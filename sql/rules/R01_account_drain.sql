-- R01 account drain (account takeover)
-- sender moves almost their whole balance in one go
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE oldbalanceorg > 0
  AND amount >= %(drain_ratio)s * oldbalanceorg
  AND amount >= %(min_amount)s;
