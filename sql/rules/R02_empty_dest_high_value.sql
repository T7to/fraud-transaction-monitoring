-- R02 Empty destination, high value (mule / pass-through account):
-- a large transfer to an account whose balance is 0 before and after,
-- meaning the money does not stay there.
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE type = 'TRANSFER'
  AND amount >= %(min_amount)s
  AND oldbalancedest = 0
  AND newbalancedest = 0;
