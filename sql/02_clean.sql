DROP TABLE IF EXISTS transactions_clean;

CREATE TABLE transactions_clean AS
SELECT
    txn_id,
    step,
    (step - 1) / 24 + 1      AS day,
    mod(step - 1, 24)        AS hour_of_day,  -- mod() not the percent sign, psycopg2 chokes on it
    type,
    amount,
    nameorig,
    oldbalanceorg,
    newbalanceorig,
    namedest,
    oldbalancedest,
    newbalancedest,
    isfraud,
    isflaggedfraud
FROM transactions_raw
WHERE type = ANY (%(monitored_types)s);

ALTER TABLE transactions_clean ADD PRIMARY KEY (txn_id);
CREATE INDEX ON transactions_clean (namedest, step);
CREATE INDEX ON transactions_clean (step);
CREATE INDEX ON transactions_clean (day);

ANALYZE transactions_clean;