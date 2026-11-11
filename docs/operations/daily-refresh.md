---
title: Daily refresh and data publishing
type: operation
created: 2026-11-11
updated: 2026-11-11
sources:
  - code: .github/workflows/daily-refresh.yml
  - code: src/dashboard/app.py
  - code: src/ingestion/irceline.py
  - code: src/ingestion/weather.py
  - code: dbt/models/staging/stg_irceline.sql
  - code: requirements.txt
verified_at: 9b87f25
---

# Daily refresh and data publishing

The live Streamlit dashboard is kept fresh by a scheduled GitHub Actions workflow, not by
Airflow. The Airflow DAG in Docker Compose (`dags/air_quality_dag.py`) runs the same
steps locally.

## Flow

The workflow runs daily at 06:00 UTC (`.github/workflows/daily-refresh.yml:9`), with a
manual "Run workflow" button that takes a `lookback_hours` input (default 30, use 168
for a 7-day backfill). One job, steps in order:

1. Restore the raw Parquet history from the `raw-data.tar.gz` asset on the `data-latest`
   release (`.github/workflows/daily-refresh.yml:51`)
2. Ingest IRCELINE + Open-Meteo (`src/ingestion/run_all.py`), exits 1 if either fails
3. `dbt run` on a freshly deleted warehouse file
   (`.github/workflows/daily-refresh.yml:76`), then `dbt test`
4. Great Expectations (`src/quality/validate.py`)
5. Write the date range to the run's step summary
6. Upload `raw-data.tar.gz`, then `air_quality.duckdb`, to the `data-latest` pre-release
   with `--clobber` (`.github/workflows/daily-refresh.yml:101`)

Any failing step stops the job before publish, so the dashboard keeps the last good file.

The dashboard downloads the release asset (`src/dashboard/app.py:31`), caches the
connection for an hour (`src/dashboard/app.py:70`) and falls back to the warehouse file
committed on `main` (stale, May 2026) if the download fails
(`src/dashboard/app.py:119` shows a caption when that happens). "Data up to" under the
header is `max(measurement_date)` from `mart_daily_aqi`.

Why a release asset and not commits: a binary committed daily grows git history forever
and triggers CI plus a Streamlit redeploy each day. A rolling release asset is replaced in
place and has a stable URL.

## Traps

> ⚠️ History lives only in the raw Parquet archive, not in the warehouse. dbt rebuilds
> every table from `data/raw/*.parquet` (`dbt/models/staging/stg_irceline.sql:10`), and a
> GitHub runner starts empty. Losing or overwriting `raw-data.tar.gz` loses all history,
> even though the old `.duckdb` looked complete.

> ⚠️ The restore step must fail on any error other than "release not found"
> (`.github/workflows/daily-refresh.yml:55`). Treating a network error as "no history"
> would publish a one-day archive over the full one.

> ⚠️ Raw file names carry a time suffix (`src/ingestion/irceline.py:193`,
> `src/ingestion/weather.py:157`). With date-only names, a second run on the same day
> overwrote the first, so a short re-run after a 7-day backfill would drop six days.

> ⚠️ DuckDB is pinned to the same version in the workflow
> (`.github/workflows/daily-refresh.yml:49`) and in `requirements.txt:10`, which Streamlit
> Cloud installs. A file written by a newer DuckDB may not open in an older one; bump both
> together.

> ⚠️ Upload order matters: raw archive first, warehouse second
> (`.github/workflows/daily-refresh.yml:109`). If the second upload fails, the next run
> still has complete history.

> ⚠️ GitHub disables scheduled workflows in a public repo after 60 days without commits.
> It emails first; re-enable from the Actions tab.

> ⚠️ `gh release create` tags the commit at the tip of `main`. If `main` is ever rewritten,
> move the `data-latest` tag too, or the old commit stays reachable through it.

## Operating it

- Run on demand: Actions tab, "Daily refresh", "Run workflow", or
  `gh workflow run daily-refresh.yml -f lookback_hours=168`
- Check what is live: `gh release view data-latest`; the run page's summary shows the date
  range that was published
- Starting history over: delete the `raw-data.tar.gz` asset; the next run starts empty
