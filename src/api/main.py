"""
FastAPI serving layer for Belgium Air Quality data.

Endpoints:
    GET /stations              — List all stations with summary stats
    GET /stations/{id}/daily   — Daily AQI for a station
    GET /nearby                — Stations within N km of a point (geo query)
    GET /health                — Pipeline health check
"""

import math
from datetime import date
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="Belgium Air Quality API",
    description="Serving BelAQI data from IRCELINE measurements",
    version="1.0.0",
)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "warehouse" / "air_quality.duckdb"


def clean_for_json(df):
    """Replace NaN/Infinity with None so JSON can serialize it."""
    records = df.to_dict(orient="records")
    for row in records:
        for key, val in row.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                row[key] = None
    return records


def get_db():
    """Get a read-only DuckDB connection."""
    return duckdb.connect(str(DB_PATH), read_only=True)


@app.get("/health")
def health_check():
    """Check if the warehouse is accessible and has recent data."""
    try:
        con = get_db()
        result = con.execute(
            "select max(measurement_date) as latest from main_marts.mart_daily_aqi"
        ).fetchone()
        con.close()
        return {
            "status": "healthy",
            "latest_data": str(result[0]) if result else None,
            "db_path": str(DB_PATH),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/stations")
def list_stations(
    min_belaqi: int | None = Query(None, ge=1, le=10, description="Filter by min avg BelAQI"),
):
    """List all stations with summary statistics."""
    con = get_db()
    query = "select * from main_marts.mart_station_summary where 1=1"
    params = []

    if min_belaqi is not None:
        query += " and mean_belaqi >= ?"
        params.append(min_belaqi)

    query += " order by mean_belaqi desc"

    result = con.execute(query, params).fetchdf()
    con.close()
    return clean_for_json(result)


@app.get("/stations/{station_id}/daily")
def station_daily(
    station_id: str,
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Get daily AQI data for a specific station."""
    con = get_db()
    query = "select * from main_marts.mart_daily_aqi where station_id = ?"
    params = [station_id]

    if start_date:
        query += " and measurement_date >= ?"
        params.append(start_date)
    if end_date:
        query += " and measurement_date <= ?"
        params.append(end_date)

    query += " order by measurement_date desc"

    result = con.execute(query, params).fetchdf()
    con.close()

    if result.empty:
        raise HTTPException(status_code=404, detail=f"No data for station {station_id}")

    return clean_for_json(result)


@app.get("/nearby")
def nearby_stations(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(10, description="Search radius in km"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """
    Find stations within a given radius of a coordinate.
    Uses the Haversine approximation for distance calculation.
    """
    con = get_db()

    query = """
    with distances as (
        select
            *,
            6371 * acos(
                cos(radians(?)) * cos(radians(station_lat)) *
                cos(radians(station_lon) - radians(?)) +
                sin(radians(?)) * sin(radians(station_lat))
            ) as distance_km
        from main_marts.mart_station_summary
    )
    select * from distances
    where distance_km <= ?
    order by distance_km asc
    limit ?
    """

    result = con.execute(query, [lat, lon, lat, radius_km, limit]).fetchdf()
    con.close()
    return clean_for_json(result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
