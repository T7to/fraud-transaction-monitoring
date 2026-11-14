import logging
from pathlib import Path

from src.db import query_df

logger = logging.getLogger(__name__)


def export_alert_queue(conn, cfg, run_id):
    with open("sql/alert_queue.sql") as f:
        sql = f.read()
    queue = query_df(conn, sql, {"run_id": run_id, "rules": cfg["report"]["queue_rules"]})

    Path("reports").mkdir(exist_ok=True)
    queue.to_csv("reports/alert_queue.csv", index=False)
    logger.info("Saved %d alerts to reports/alert_queue.csv", len(queue))
