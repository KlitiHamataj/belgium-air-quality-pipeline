---
title: Metabase (local BI)
type: operation
created: 2026-11-13
updated: 2026-11-13
sources:
  - code: docker/Dockerfile.metabase
  - code: docker-compose.yml
  - code: src/bi/snapshot.py
  - code: dags/air_quality_dag.py
  - code: tests/test_snapshot.py
  - ext:  https://github.com/motherduckdb/metabase_duckdb_driver
verified_at: fe00500
---

# Metabase (local BI)

An optional, local-only Metabase for self-service questions on the dbt marts. It is not
deployed anywhere; the public dashboard stays on Streamlit (see [[daily-refresh]]).
Setup steps for users are in the README's "Metabase" section; this page covers how it
works and what breaks it.

## How it fits

- `src/bi/snapshot.py` copies every **base table** of `data/warehouse/air_quality.duckdb`
  into `data/warehouse/metabase/air_quality.duckdb`. It builds a `.tmp` file, checkpoints
  it, then swaps it in with `os.replace`
- The Airflow DAG runs it as `publish_metabase_snapshot`, after `data_quality_check`
  (`dags/air_quality_dag.py`), so Metabase only sees data that passed dbt tests and Great
  Expectations. The GitHub Actions refresh does **not** run it: the release asset is for
  Streamlit
- The `metabase` compose service is behind the `metabase` profile, so a plain
  `docker compose up` does not build it. It mounts `data/warehouse/metabase` read-only at
  `/warehouse`, and keeps its own application database (H2) in the `metabase-data` volume
- The DuckDB data source is added once by hand in the UI with database file
  `/warehouse/air_quality.duckdb` and the read-only option on. It persists in the volume

> ⚠️ **Never point Metabase at the live warehouse.** Metabase pools JDBC connections and
> keeps them open for hours. A DuckDB connection, even a read-only one, holds a file lock
> that makes the next `dbt run` (or the Airflow `dbt_run` task) fail to open the file for
> writing. The snapshot exists only to avoid this.

> ⚠️ **Mount the snapshot directory, not the file.** The snapshot is replaced by rename. A
> single-file bind mount pins the old inode, so the container would never see a new copy.

> ⚠️ **The snapshot skips views on purpose.** The staging views call
> `read_parquet('../data/raw/...')` with paths relative to `dbt/`. Those paths do not
> resolve inside the Metabase container, so the views would appear there as tables that
> error when opened. Only `main_intermediate` and `main_marts` tables are copied.

> ⚠️ **The DuckDB driver version must read the pipeline's file format.** Driver `1.5.3.0`
> bundles DuckDB 1.5.3, matching `duckdb==1.5.3` in `requirements.txt`. When you bump
> DuckDB, bump `DUCKDB_DRIVER_VERSION` in `docker/Dockerfile.metabase` to the release
> with the same DuckDB version.

> ⚠️ **Don't switch to the official `metabase/metabase` image.** It is Alpine-based, and
> the DuckDB JDBC driver needs glibc. `docker/Dockerfile.metabase` builds on Debian
> (`eclipse-temurin:21-jre-jammy`) for that reason.

> ⚠️ **New data appears only after the pool recycles.** A connection Metabase already has
> open keeps reading the replaced file. Restart the container to see a fresh snapshot right
> away.
