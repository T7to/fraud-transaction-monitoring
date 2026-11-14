-- R02 big transfer to an account that stays at 0 before and after
-- (money passes straight through -> looks like a mule account)
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE type = 'TRANSFER'
  AND amount >= %(min_amount)s
  AND oldbalancedest = 0
  AND newbalancedest = 0;
