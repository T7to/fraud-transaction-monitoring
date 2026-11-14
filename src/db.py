import io
import logging
import os
from decimal import Decimal

import pandas as pd
import psycopg2
import yaml
from dotenv import load_dotenv
from psycopg2 import sql as pgsql

logger = logging.getLogger(__name__)


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def get_connection(cfg):
    # password only comes from .env, env vars can override the rest
    load_dotenv()
    db = cfg["database"]
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", db["host"]),
        port=int(os.getenv("PGPORT", db["port"])),
        dbname=os.getenv("PGDATABASE", db["dbname"]),
        user=os.getenv("PGUSER", db["user"]),
        password=os.environ["POSTGRES_PASSWORD"],
    )
    logger.info("Connected to %s on %s", conn.info.dbname, conn.info.host)
    return conn


def run_sql_file(conn, path, params=None):
    with open(path) as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()
    logger.info("Ran %s", path)


def query_df(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        columns = [col[0] for col in cur.description]
    df = pd.DataFrame(rows, columns=columns)

    # NUMERIC comes back as Decimal, which breaks pandas maths -> make it float
    for col in df.columns:
        first = df[col].dropna().head(1)
        if not first.empty and isinstance(first.iloc[0], Decimal):
            df[col] = df[col].astype(float)
    return df


def copy_to_df(conn, query):
    # COPY is way faster than fetchall when there are millions of rows
    buffer = io.StringIO()
    with conn.cursor() as cur:
        cur.copy_expert(f"COPY ({query}) TO STDOUT WITH CSV HEADER", buffer)
    buffer.seek(0)
    df = pd.read_csv(buffer)
    logger.info("Exported %d rows via COPY", len(df))
    return df


def copy_from_df(conn, df, table):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    # table/column names can't be passed as %(x)s params, so quote them this way
    copy_sql = pgsql.SQL("COPY {} ({}) FROM STDIN WITH CSV").format(
        pgsql.Identifier(table),
        pgsql.SQL(", ").join(pgsql.Identifier(c) for c in df.columns),
    )
    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, buffer)
    conn.commit()
    logger.info("Loaded %d rows into %s", len(df), table)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    conn = get_connection(load_config())
    print(query_df(conn, "SELECT 1 AS ok"))
    conn.close()
