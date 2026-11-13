"""
Publish a read-only snapshot of the warehouse for Metabase.

Metabase keeps pooled DuckDB connections open for hours. Even a read-only
connection holds a file lock that makes the next `dbt run` fail, so Metabase
never reads the live warehouse. It reads a copy that is rebuilt here and
swapped into place atomically after the pipeline's checks pass.

Only materialized tables (intermediate + marts) are copied. The staging views
read raw Parquet through relative paths that do not resolve inside the
Metabase container, so they would only show up there as broken tables.

    python -m src.bi.snapshot
"""

import logging
import os
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAREHOUSE_DIR = Path(__file__).parent.parent.parent / "data" / "warehouse"
DB_PATH = WAREHOUSE_DIR / "air_quality.duckdb"
SNAPSHOT_PATH = WAREHOUSE_DIR / "metabase" / "air_quality.duckdb"


def _sql_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def publish_snapshot(source: Path = DB_PATH, dest: Path = SNAPSHOT_PATH) -> list[str]:
    """Copy every base table of `source` into `dest`, replacing it atomically.

    Returns the copied tables as "schema.table".
    """
    if not source.exists():
        raise FileNotFoundError(f"Warehouse not found: {source}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    for leftover in (tmp, tmp.with_name(tmp.name + ".wal")):
        leftover.unlink(missing_ok=True)

    con = duckdb.connect()
    try:
        con.execute(f"ATTACH {_sql_literal(source)} AS src (READ_ONLY)")
        con.execute(f"ATTACH {_sql_literal(tmp)} AS snap")
        tables = con.execute(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_catalog = 'src' and table_type = 'BASE TABLE'
            order by 1, 2
            """
        ).fetchall()
        if not tables:
            raise RuntimeError(f"No tables to snapshot in {source}; run dbt first")

        for schema, table in tables:
            con.execute(f'CREATE SCHEMA IF NOT EXISTS snap."{schema}"')
            con.execute(
                f'CREATE TABLE snap."{schema}"."{table}" AS '
                f'SELECT * FROM src."{schema}"."{table}"'
            )
        # Flush everything into the file so no .wal is left beside it
        con.execute("CHECKPOINT snap")
        con.execute("DETACH snap")
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    con.close()

    # Atomic on the same filesystem. A Metabase connection still open on the old
    # file keeps reading that file until its pool recycles the connection.
    os.replace(tmp, dest)

    copied = [f"{schema}.{table}" for schema, table in tables]
    logger.info("Published Metabase snapshot %s (%d tables)", dest, len(copied))
    return copied


if __name__ == "__main__":
    publish_snapshot()
