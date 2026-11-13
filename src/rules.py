"""Run the rule scenarios, store their alerts, and measure each rule's performance."""

import logging
from datetime import datetime

from src.db import get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)

EVALUATE_SQL = "sql/evaluate_rules.sql"

# The existing system rule, kept as the benchmark every new rule is compared against.
LEGACY_SQL = """
SELECT txn_id, step, day, amount, isfraud
FROM transactions_clean
WHERE isflaggedfraud = 1
"""


def load_enabled_rules(cfg):
    """Return {rule_id: (sql, params)} for every enabled rule, plus the legacy benchmark."""
    rules = {}
    for rule_id, rule in cfg["rules"].items():
        if rule["enabled"]:
            with open(rule["file"]) as f:
                rules[rule_id] = (f.read(), rule["params"])
    rules["LEGACY_FLAG"] = (LEGACY_SQL, {})
    return rules


def run_rules(conn, cfg, run_id):
    """Run each rule inside the database and insert its hits into alerts.

    The INSERT ... SELECT wraps the rule's own query, so millions of alerts are
    written without ever leaving PostgreSQL.
    """
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM alerts WHERE run_id = %(run_id)s AND rule_id <> 'ML_SCORE'",
            {"run_id": run_id},
        )
        for rule_id, (rule_sql, params) in load_enabled_rules(cfg).items():
            insert_sql = f"""
                INSERT INTO alerts (run_id, rule_id, txn_id, step, day, amount, isfraud)
                SELECT %(run_id)s, %(rule_id)s, r.txn_id, r.step, r.day, r.amount, r.isfraud
                FROM (
                    {rule_sql.strip().rstrip(";")}
                ) AS r
            """
            cur.execute(insert_sql, {**params, "run_id": run_id, "rule_id": rule_id})
            logger.info("%-26s %9d alerts", rule_id, cur.rowcount)
    conn.commit()


def evaluate_rules(conn, cfg, run_id):
    """Compute precision, recall and alerts/day per rule, on ALL days and the TEST period."""
    test_start_step = cfg["split"]["valid_end_step"] + 1
    run_sql_file(conn, EVALUATE_SQL, {"run_id": run_id, "test_start_step": test_start_step})
    return query_df(
        conn,
        """
        SELECT rule_id, period, alerts, true_positives, total_fraud,
               precision, recall, alerts_per_day
        FROM rule_performance
        WHERE run_id = %(run_id)s
        ORDER BY period, rule_id
        """,
        {"run_id": run_id},
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_rules(conn, cfg, run_id)
        print(evaluate_rules(conn, cfg, run_id).to_string(index=False))
    finally:
        conn.close()
