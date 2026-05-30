"""
Great Expectations v1.x data quality checks on the DuckDB warehouse.
"""

import sys
import logging
from pathlib import Path

import duckdb
import great_expectations as gx
from great_expectations.expectations import (
    ExpectTableRowCountToBeBetween,
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToBeBetween,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "warehouse" / "air_quality.duckdb"


def get_df(query: str):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(query).fetchdf()
    con.close()
    return df


def validate_table(name: str, query: str, expectations: list) -> bool:
    """Run a list of expectations against a query result."""
    logger.info(f"Validating {name}...")

    df = get_df(query)

    context = gx.get_context(mode="ephemeral")

    data_source = context.data_sources.add_pandas(f"ds_{name}")
    data_asset = data_source.add_dataframe_asset(name=f"asset_{name}")
    batch_definition = data_asset.add_batch_definition_whole_dataframe(f"batch_{name}")

    suite = context.suites.add(
        gx.ExpectationSuite(name=f"suite_{name}", expectations=expectations)
    )

    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name=f"validation_{name}",
            data=batch_definition,
            suite=suite,
        )
    )

    result = validation_definition.run(batch_parameters={"dataframe": df})

    passed = result.success
    total = len(result.results)
    failures = [r for r in result.results if not r.success]

    if passed:
        logger.info(f"  ✓ {name}: {total} checks passed")
    else:
        logger.error(f"  ✗ {name}: {len(failures)}/{total} checks failed")
        for r in failures:
            logger.error(f"    - {r.expectation_config.type}")

    return passed


def run_all_validations():
    all_passed = True

    # Validate mart_daily_aqi
    ok = validate_table(
        "mart_daily_aqi",
        "select * from main_marts.mart_daily_aqi",
        [
            ExpectTableRowCountToBeBetween(min_value=1),
            ExpectColumnValuesToNotBeNull(column="station_id"),
            ExpectColumnValuesToNotBeNull(column="measurement_date"),
            ExpectColumnValuesToNotBeNull(column="belaqi_overall"),
            ExpectColumnValuesToBeBetween(
                column="belaqi_overall", min_value=1, max_value=10
            ),
        ],
    )
    if not ok:
        all_passed = False

    # Validate mart_station_summary
    ok = validate_table(
        "mart_station_summary",
        "select * from main_marts.mart_station_summary",
        [
            ExpectTableRowCountToBeBetween(min_value=1),
            ExpectColumnValuesToBeUnique(column="station_id"),
            ExpectColumnValuesToBeBetween(
                column="station_lat", min_value=49.5, max_value=51.6
            ),
            ExpectColumnValuesToBeBetween(
                column="station_lon", min_value=2.3, max_value=6.5
            ),
        ],
    )
    if not ok:
        all_passed = False

    if not all_passed:
        sys.exit(1)

    logger.info("All validations passed")


if __name__ == "__main__":
    run_all_validations()