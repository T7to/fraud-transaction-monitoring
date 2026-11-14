import json
import logging
from datetime import datetime

from src.db import get_connection, load_config, query_df
from src.features import KEY_FEATURES
from src.load import count_csv_rows

logger = logging.getLogger(__name__)


def count(conn, sql, params=None):
    return int(query_df(conn, sql, params).iloc[0, 0])


def run_controls(conn, cfg, run_id):
    results = []

    def check(control_id, expected, actual, passed, fail_status="FAIL"):
        status = "PASS" if passed else fail_status
        results.append((control_id, status, str(expected), str(actual)))
        logger.info("%-12s %-4s expected=%s actual=%s", control_id, status, expected, actual)

    #every CSV row reached the database.
    csv_rows = count_csv_rows(cfg["data"]["csv_path"])
    raw_rows = count(conn, "SELECT COUNT(*) FROM transactions_raw")
    check("C01_LOAD", csv_rows, raw_rows, csv_rows == raw_rows)

    #the clean table holds exactly the monitored types from raw.
    expected = count(conn, "SELECT COUNT(*) FROM transactions_raw WHERE type = ANY(%(t)s)",
                     {"t": cfg["data"]["monitored_types"]})
    actual = count(conn, "SELECT COUNT(*) FROM transactions_clean")
    check("C02_SCOPE", expected, actual, expected == actual)

    #one feature row per clean transaction, and no empty key features.
    feature_rows = count(conn, "SELECT COUNT(*) FROM features")
    null_filter = " OR ".join(f"{col} IS NULL" for col in KEY_FEATURES)
    null_rows = count(conn, f"SELECT COUNT(*) FROM features WHERE {null_filter}")
    check("C03_FEATURES", f"{actual} rows, 0 nulls", f"{feature_rows} rows, {null_rows} nulls",
          feature_rows == actual and null_rows == 0)

    # every alert points to a real monitored transaction.
    orphans = count(conn, """
        SELECT COUNT(*) FROM alerts a
        LEFT JOIN transactions_clean t ON t.txn_id = a.txn_id
        WHERE t.txn_id IS NULL
    """)
    check("C04_ALERTS", 0, orphans, orphans == 0)

    #model alerts per day stay within 30 percent of the team's capacity (warning only).
    budget = cfg["model"]["alert_budget_per_day"]
    with open("artifacts/metrics_full.json") as f:
        per_day = json.load(f)["test_alerts"]["alerts_per_day"]
    check("C05_BUDGET", budget, per_day, abs(per_day - budget) <= 0.3 * budget, fail_status="WARN")

    with conn.cursor() as cur:
        cur.execute("DELETE FROM control_log WHERE run_id = %(r)s", {"r": run_id})
        for control_id, status, expected, actual in results:
            cur.execute(
                "INSERT INTO control_log (run_id, control_id, status, expected, actual) "
                "VALUES (%(r)s, %(c)s, %(s)s, %(e)s, %(a)s)",
                {"r": run_id, "c": control_id, "s": status, "e": expected, "a": actual},
            )
    conn.commit()

    return all(status != "FAIL" for _, status, _, _ in results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        ok = run_controls(conn, cfg, datetime.now().strftime("%Y%m%d_%H%M%S"))
        logger.info("All controls passed" if ok else "Some controls FAILED")
    finally:
        conn.close()
