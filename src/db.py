"""db helpers: the only module that talks to Postgresql directly"""

import logging
import os

import psycopg2
import yaml
from dotenv import load_dotenv
import pandas as pd
from decimal import Decimal


import io
from psycopg2 import sql as pgsql

logger = logging.getLogger(__name__)

def load_config(path="config.yaml"):
    """read the YAML config so every threshold lives in one reviewed file"""
    with open(path) as f:
        return yaml.safe_load(f)

def get_connection(cfg):
    """Open a PostgreSQL connection.

    Environment variables override config.yaml so the same code can point to
    a laptop, test or production database without editing files.
    The password only ever comes from the environment (.env), never from config.
    """
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
    """Execute a .sql file so all SQL logic stays in versioned files, not Python strings.

    params fills %(name)s placeholders safely (no string formatting of values).
    """
    with open(path) as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()
    logger.info("Ran %s", path)


def query_df(conn, sql, params=None):
    """Run a SELECT and return a DataFrame, for small result sets analysed in Python.

    NUMERIC columns arrive as Decimal; convert them to float so pandas maths works.
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        columns = [col[0] for col in cur.description]
    df = pd.DataFrame(rows, columns=columns)
    for col in df.columns:
        first = df[col].dropna().head(1)
        if not first.empty and isinstance(first.iloc[0], Decimal):
            df[col] = df[col].astype(float)
    return df

def copy_to_df(conn, query):
    """Export a large query result to pandas via COPY, much faster than fetchall on millions of rows."""
    buffer = io.StringIO()
    copy_sql = f"COPY ({query}) TO STDOUT WITH CSV HEADER"
    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, buffer)
    buffer.seek(0)
    df = pd.read_csv(buffer)
    logger.info("Exported %d rows via COPY", len(df))
    return df


def copy_from_df(conn, df, table):
    """Bulk-insert a DataFrame via COPY: one data stream instead of one INSERT per row.

    Table and column names are quoted with sql.Identifier, because identifiers
    cannot be passed as %(name)s parameters.
    """
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    copy_sql = pgsql.SQL("COPY {} ({}) FROM STDIN WITH CSV").format(
        pgsql.Identifier(table),
        pgsql.SQL(", ").join(pgsql.Identifier(c) for c in df.columns),
    )
    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, buffer)
    conn.commit()
    logger.info("Loaded %d rows into %s via COPY", len(df), table)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE t (a INT, b NUMERIC)")
        copy_from_df(conn, pd.DataFrame({"a": [1, 2, 3], "b": [1.5, 2.5, 3.5]}), "t")
        print(copy_to_df(conn, "SELECT * FROM t"))
    finally:
        conn.close()