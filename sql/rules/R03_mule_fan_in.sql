-- R03 mule fan-in: one account gets money from lots of different people in a day.
-- runs end of day, flags all of that account's transactions for the day
SELECT t.txn_id, t.step, t.day, t.amount, t.isfraud
FROM transactions_clean t
JOIN dest_daily d
  ON d.namedest = t.namedest
 AND d.day = t.day
WHERE d.distinct_senders >= %(min_senders)s
  AND d.total_amount >= %(min_total)s;
