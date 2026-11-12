import logging
import time

from src.db import get_connection, load_config

logger = logging.getLogger(__name__)

RAW_COLUMNS = [
    "step", "type", "amount",
    "nameorig", "oldbalanceorg", "newbalanceorig",
    "namedest", "oldbalancedest", "newbalancedest",
    "isfraud", "isflaggedfraud",
]


def count_csv_rows(path):
    """Count data rows (excluding header)"""
    with open(path) as f:
        return sum(1 for _ in f) - 1


def load_raw(conn, csv_path):
    """Replace transactions_raw with the CSV contents and return (csv_rows, loaded_rows)."""
    csv_rows = count_csv_rows(csv_path)
    columns = ", ".join(RAW_COLUMNS)
    copy_sql = f"COPY transactions_raw ({columns}) FROM STDIN WITH CSV HEADER"

    start = time.time()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE transactions_raw RESTART IDENTITY")
        with open(csv_path) as f:
            cur.copy_expert(copy_sql, f)
        cur.execute("SELECT COUNT(*) FROM transactions_raw")
        loaded_rows = cur.fetchone()[0]
    conn.commit()

    logger.info(
        "Loaded %d of %d CSV rows in %.1fs", loaded_rows, csv_rows, time.time() - start
    )
    return csv_rows, loaded_rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        load_raw(conn, cfg["data"]["csv_path"])
    finally:
        conn.close()
