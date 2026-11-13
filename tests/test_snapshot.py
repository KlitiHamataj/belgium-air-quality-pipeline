"""Unit tests for the Metabase warehouse snapshot."""

import duckdb
import pytest

from src.bi.snapshot import publish_snapshot


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "air_quality.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA main_marts")
    con.execute("CREATE TABLE main_marts.mart_daily_aqi AS SELECT 1 AS station_id, 3 AS belaqi")
    con.execute("CREATE SCHEMA main_staging")
    con.execute("CREATE VIEW main_staging.stg_irceline AS SELECT * FROM main_marts.mart_daily_aqi")
    con.close()
    return path


def test_copies_tables_but_not_views(warehouse, tmp_path):
    dest = tmp_path / "metabase" / "air_quality.duckdb"

    copied = publish_snapshot(warehouse, dest)

    assert copied == ["main_marts.mart_daily_aqi"]
    con = duckdb.connect(str(dest), read_only=True)
    assert con.execute("SELECT belaqi FROM main_marts.mart_daily_aqi").fetchall() == [(3,)]
    views = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_type = 'VIEW'"
    )
    assert views.fetchone() == (0,)
    con.close()


def test_replaces_existing_snapshot_and_leaves_no_temp_files(warehouse, tmp_path):
    dest = tmp_path / "metabase" / "air_quality.duckdb"
    publish_snapshot(warehouse, dest)

    con = duckdb.connect(str(warehouse))
    con.execute("UPDATE main_marts.mart_daily_aqi SET belaqi = 7")
    con.close()
    publish_snapshot(warehouse, dest)

    con = duckdb.connect(str(dest), read_only=True)
    assert con.execute("SELECT belaqi FROM main_marts.mart_daily_aqi").fetchall() == [(7,)]
    con.close()
    assert sorted(p.name for p in dest.parent.iterdir()) == ["air_quality.duckdb"]


def test_source_stays_writable_after_snapshot(warehouse, tmp_path):
    publish_snapshot(warehouse, tmp_path / "snap.duckdb")

    con = duckdb.connect(str(warehouse))
    con.execute("CREATE TABLE main_marts.after AS SELECT 1")
    con.close()


def test_missing_warehouse_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        publish_snapshot(tmp_path / "nope.duckdb", tmp_path / "snap.duckdb")


def test_empty_warehouse_raises_and_cleans_up(tmp_path):
    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()
    dest = tmp_path / "metabase" / "air_quality.duckdb"

    with pytest.raises(RuntimeError):
        publish_snapshot(empty, dest)
    assert list(dest.parent.iterdir()) == []
