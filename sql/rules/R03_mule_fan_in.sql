-- R03 Mule fan-in (collection account):
-- a destination receives money from many different senders in one day.
-- End-of-day rule: alerts every transaction to that destination on that day.
SELECT t.txn_id, t.step, t.day, t.amount, t.isfraud
FROM transactions_clean t
JOIN dest_daily d
  ON d.namedest = t.namedest
 AND d.day = t.day
WHERE d.distinct_senders >= %(min_senders)s
  AND d.total_amount >= %(min_total)s;
