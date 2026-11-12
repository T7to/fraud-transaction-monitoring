"""Run data quality checks, log them to dq_results, and stop the pipeline on CRITICAL failures."""

import logging
from datetime import datetime

from src.db import copy_from_df, get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)

QUALITY_SQL = "sql/01_quality_checks.sql"


class DataQualityError(Exception):
    """Raised when a CRITICAL check fails: the data must not be used downstream."""


def assign_status(row):
    """Map a check result to PASS / WARN / FAIL.

    Severity decides the action: CRITICAL failures block the run, WARNING asks
    for review, INFO is recorded for trend monitoring but never blocks.
    """
    if row["failed_rows"] == 0 or row["severity"] == "INFO":
        return "PASS"
    if row["severity"] == "CRITICAL":
        return "FAIL"
    return "WARN"


def run_quality_checks(conn, cfg, run_id):
    """Run all DQ checks, store them under run_id, and raise if any CRITICAL check fails."""
    with open(QUALITY_SQL) as f:
        results = query_df(conn, f.read(), cfg["quality"])

    results["failed_pct"] = (100 * results["failed_rows"] / results["total_rows"]).round(4)
    results["status"] = results.apply(assign_status, axis=1)
    results.insert(0, "run_id", run_id)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM dq_results WHERE run_id = %(run_id)s", {"run_id": run_id})
    copy_from_df(conn, results, "dq_results")

    for r in results.itertuples():
        logger.info("%-25s %-8s %-4s %d rows", r.check_name, r.severity, r.status, r.failed_rows)

    failed = results.loc[results["status"] == "FAIL", "check_name"].tolist()
    if failed:
        raise DataQualityError(f"CRITICAL data quality checks failed: {failed}")
    return results

CLEAN_SQL = "sql/02_clean.sql"


def build_clean_table(conn, cfg):
    """Create transactions_clean with only the monitored types; returns its row count."""
    run_sql_file(conn, CLEAN_SQL, {"monitored_types": cfg["data"]["monitored_types"]})
    rows = query_df(conn, "SELECT COUNT(*) AS n FROM transactions_clean")["n"].iloc[0]
    logger.info("transactions_clean built with %d rows", rows)
    return rows

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_quality_checks(conn, cfg, run_id)
        build_clean_table(conn, cfg)
    finally:
        conn.close()