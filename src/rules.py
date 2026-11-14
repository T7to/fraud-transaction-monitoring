import logging
from datetime import datetime

from src.db import get_connection, load_config, query_df, run_sql_file

logger = logging.getLogger(__name__)

# the bank's existing flag, kept as a benchmark to compare against
LEGACY_SQL = "SELECT txn_id, step, day, amount, isfraud FROM transactions_clean WHERE isflaggedfraud = 1"


def load_rules(cfg):
    rules = {}
    for rule_id, rule in cfg["rules"].items():
        if rule["enabled"]:
            with open(rule["file"]) as f:
                rules[rule_id] = (f.read(), rule["params"])
    rules["LEGACY_FLAG"] = (LEGACY_SQL, {})
    return rules


def run_rules(conn, cfg, run_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alerts WHERE run_id = %(run_id)s", {"run_id": run_id})

        for rule_id, (rule_sql, params) in load_rules(cfg).items():
            # wrap the rule query in an INSERT so the alerts never leave postgres (much faster)
            insert_sql = f"""
                INSERT INTO alerts (run_id, rule_id, txn_id, step, day, amount, isfraud)
                SELECT %(run_id)s, %(rule_id)s, r.txn_id, r.step, r.day, r.amount, r.isfraud
                FROM ({rule_sql.strip().rstrip(";")}) AS r
            """
            cur.execute(insert_sql, {**params, "run_id": run_id, "rule_id": rule_id})
            logger.info("%-26s %9d alerts", rule_id, cur.rowcount)
    conn.commit()


def evaluate_rules(conn, cfg, run_id):
    test_start = cfg["split"]["valid_end_step"] + 1
    run_sql_file(conn, "sql/evaluate_rules.sql", {"run_id": run_id, "test_start_step": test_start})
    return query_df(conn, """
        SELECT rule_id, period, alerts, true_positives, total_fraud, precision, recall, alerts_per_day
        FROM rule_performance
        WHERE run_id = %(run_id)s
        ORDER BY period, rule_id
    """, {"run_id": run_id})


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
