import logging
from datetime import datetime

from src.db import copy_from_df, get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    pass


def get_status(row):
    # INFO never blocks anything, it's just there so we can see it over time
    if row["failed_rows"] == 0 or row["severity"] == "INFO":
        return "PASS"
    if row["severity"] == "CRITICAL":
        return "FAIL"
    return "WARN"


def run_quality_checks(conn, cfg, run_id):
    with open("sql/01_quality_checks.sql") as f:
        results = query_df(conn, f.read(), cfg["quality"])

    results["failed_pct"] = (100 * results["failed_rows"] / results["total_rows"]).round(4)
    results["status"] = results.apply(get_status, axis=1)
    results.insert(0, "run_id", run_id)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM dq_results WHERE run_id = %(r)s", {"r": run_id})
    copy_from_df(conn, results, "dq_results")

    for r in results.itertuples():
        logger.info("%-25s %-8s %-4s %d rows", r.check_name, r.severity, r.status, r.failed_rows)

    # results are saved first, so we still have the evidence if we stop here
    failed = results.loc[results["status"] == "FAIL", "check_name"].tolist()
    if failed:
        raise DataQualityError(f"critical checks failed: {failed}")


def build_clean_table(conn, cfg):
    run_sql_file(conn, "sql/02_clean.sql", {"monitored_types": cfg["data"]["monitored_types"]})
    rows = query_df(conn, "SELECT COUNT(*) AS n FROM transactions_clean")["n"].iloc[0]
    logger.info("transactions_clean: %d rows", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        run_quality_checks(conn, cfg, datetime.now().strftime("%Y%m%d_%H%M%S"))
        build_clean_table(conn, cfg)
    finally:
        conn.close()
