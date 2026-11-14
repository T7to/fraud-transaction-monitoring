import logging

from src.db import get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)

# these should never be NULL (checked in controls C03).
# the ratio features can be NULL on purpose, it means "no history yet"
KEY_FEATURES = [
    "is_transfer", "log_amount", "orig_zero_balance_before", "orig_drained",
    "error_balance_orig", "error_balance_dest", "dest_balance_unchanged",
    "dest_prior_txn_24h", "dest_prior_amount_24h", "dest_prior_txn_all",
    "hours_since_dest_last_txn", "dest_first_seen",
]


def build_features(conn):
    run_sql_file(conn, "sql/03_features.sql")
    rows = query_df(conn, "SELECT COUNT(*) AS n FROM features")["n"].iloc[0]
    logger.info("features: %d rows", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    conn = get_connection(load_config())
    try:
        build_features(conn)
    finally:
        conn.close()
