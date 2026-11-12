"""Build the feature table and dest_daily in SQL, then check completeness."""

import logging

from src.db import get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)

FEATURES_SQL = "sql/03_features.sql"

# Features that must never be NULL. Ratios (pct_balance_moved, amount_vs_dest_avg,
# dest_prior_avg_amount) can be NULL by design: "undefined"
KEY_FEATURES = [
    "is_transfer", "log_amount", "orig_zero_balance_before", "orig_drained",
    "error_balance_orig", "error_balance_dest", "dest_balance_unchanged",
    "dest_prior_txn_24h", "dest_prior_amount_24h", "dest_prior_txn_all",
    "hours_since_dest_last_txn", "dest_first_seen",
]


def build_features(conn):
    """Create features and dest_daily, then verify completeness against transactions_clean."""
    run_sql_file(conn, FEATURES_SQL)

    null_checks = ", ".join(
        f"COUNT(*) FILTER (WHERE {col} IS NULL) AS {col}" for col in KEY_FEATURES
    )
    nulls = query_df(conn, f"SELECT {null_checks} FROM features").iloc[0]
    counts = query_df(conn, """
        SELECT (SELECT COUNT(*) FROM transactions_clean) AS clean_rows,
               (SELECT COUNT(*) FROM features)           AS feature_rows
    """).iloc[0]

    logger.info("features: %d rows (clean: %d)", counts["feature_rows"], counts["clean_rows"])
    columns_with_nulls = nulls[nulls > 0].to_dict()

    if counts["feature_rows"] != counts["clean_rows"]:
        raise ValueError(f"Row count mismatch: {counts.to_dict()}")
    if columns_with_nulls:
        raise ValueError(f"Nulls in key features: {columns_with_nulls}")
    logger.info("Feature completeness OK: no nulls in %d key features", len(KEY_FEATURES))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        build_features(conn)
    finally:
        conn.close()