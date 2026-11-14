import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from src.controls import run_controls
from src.db import get_connection, load_config, run_sql_file
from src.features import build_features
from src.load import load_raw
from src.model import run_model
from src.quality import build_clean_table, run_quality_checks
from src.rules import evaluate_rules, run_rules

logger = logging.getLogger("pipeline")


def setup_logging(run_id):

    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(f"logs/run_{run_id}.log")],
    )


def stage(name, func, *args):
    start = time.time()
    logger.info("----- %s -----", name)
    result = func(*args)
    logger.info("%s done in %.1fs", name, time.time() - start)
    return result


def run_stages(conn, cfg, run_id, skip_load):
    if not skip_load:
        stage("load", load_raw, conn, cfg["data"]["csv_path"])
    stage("quality", run_quality_checks, conn, cfg, run_id)
    stage("clean", build_clean_table, conn, cfg)
    stage("features", build_features, conn)
    stage("rules", run_rules, conn, cfg, run_id)
    stage("evaluate rules", evaluate_rules, conn, cfg, run_id)
    stage("model", run_model, conn, cfg)
    return stage("controls", run_controls, conn, cfg, run_id)


def set_status(conn, run_id, status):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE pipeline_runs SET status = %(status)s, ended_at = now() WHERE run_id = %(run_id)s",
            {"run_id": run_id, "status": status},
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-load", action="store_true", help="reuse the data already in postgres")
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    setup_logging(run_id)
    cfg = load_config()
    conn = get_connection(cfg)

    run_sql_file(conn, "sql/00_schema.sql")
    with conn.cursor() as cur:
        cur.execute("INSERT INTO pipeline_runs (run_id, status) VALUES (%(run_id)s, 'RUNNING')", {"run_id": run_id})
    conn.commit()

    try:
        controls_ok = run_stages(conn, cfg, run_id, args.skip_load)
        status = "SUCCESS" if controls_ok else "CONTROLS_FAILED"
    except Exception:
        logger.exception("Pipeline crashed")
        conn.rollback()
        status = "FAILED"

    set_status(conn, run_id, status)
    conn.close()
    logger.info("Run %s finished: %s", run_id, status)
    sys.exit(0 if status == "SUCCESS" else 1)


if __name__ == "__main__":
    main()