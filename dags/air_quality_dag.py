"""
Airflow DAG: Belgium Air Quality Pipeline

Runs daily at 06:00 UTC:
1. Ingest from IRCELINE and Open-Meteo (parallel)
2. Run dbt models
3. Run dbt tests
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"

default_args = {
    "owner": "kliti",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="belgium_air_quality",
    default_args=default_args,
    description="ELT pipeline for Belgian air quality data",
    schedule_interval="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["air-quality", "belgium", "elt"],
) as dag:

    ingest_irceline = BashOperator(
        task_id="ingest_irceline",
        bash_command=f"cd {PROJECT_DIR} && python -m src.ingestion.irceline",
    )

    ingest_weather = BashOperator(
        task_id="ingest_weather",
        bash_command=f"cd {PROJECT_DIR} && python -m src.ingestion.weather",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt test --profiles-dir .",
    )

# ─── Data Quality ────────────────────────────────────────────────

    data_quality = BashOperator(
        task_id="data_quality_check",
        bash_command=f"cd {PROJECT_DIR} && python -m src.quality.validate",
    )

    [ingest_irceline, ingest_weather] >> dbt_run >> dbt_test >> data_quality