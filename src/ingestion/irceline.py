"""
IRCELINE SOS API client.

Pulls air quality measurements from Belgium's official monitoring network.
Endpoint docs: https://geo.irceline.be/sos/api/v1/
Available pollutants: PM10, PM2.5, NO2, O3, SO2, CO, BC (black carbon)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from tracemalloc import stop

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from tenacity import retry, stop_after_attempt, wait_exponential

from src.ingestion.config import settings

logger = logging.getLogger(__name__)

BASE_URL = settings.irceline_sos_url

# IRCELINE phenomenon IDs for key pollutants
# These map to the SOS API's internal IDs — discovered via /phenomena endpoint
POLLUTANT_IDS = {
    "PM10": 5,
    "PM2.5": 6001,
    "NO2": 8,
    "O3": 7,
    "SO2": 1,
    "CO": 2,
    "BC": 6015,
}

# Schema for raw IRCELINE data
IRCELINE_SCHEMA = pa.schema(
    [
        pa.field("station_id", pa.string()),
        pa.field("station_label", pa.string()),
        pa.field("latitude", pa.float64()),
        pa.field("longitude", pa.float64()),
        pa.field("pollutant", pa.string()),
        pa.field("timestamp", pa.timestamp("ms")),
        pa.field("value", pa.float64()),
        pa.field("unit", pa.string()),
        pa.field("ingested_at", pa.timestamp("ms")),
    ]
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
def _get(client: httpx.Client, endpoint: str, params: dict | None = None) -> dict:
    """GET request with retry logic."""
    url = f"{BASE_URL}/{endpoint}"
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_stations(client: httpx.Client) -> list[dict]:
    """Fetch all active monitoring stations."""
    stations = _get(client, "stations", params={"expanded": "true"})
    logger.info(f"Fetched {len(stations)} IRCELINE stations")
    return stations


def fetch_timeseries_data(
    client: httpx.Client,
    timeseries_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch measurement values for a specific timeseries (station + pollutant combo)."""
    params = {
        "timespan": f"{start.isoformat()}/{end.isoformat()}",
    }
    data = _get(client, f"timeseries/{timeseries_id}/getData", params=params)
    return data.get("values", [])


def fetch_timeseries_metadata(client: httpx.Client) -> list[dict]:
    """
    Fetch all available timeseries with expanded metadata.
    Each timeseries = one station + one pollutant combination.
    """
    timeseries = _get(
        client,
        "timeseries",
        params={"expanded": "true", "offset": 0, "limit": 5000},
    )
    logger.info(f"Fetched metadata for {len(timeseries)} timeseries")
    return timeseries


def ingest_irceline(
    lookback_hours: int = 24,
    output_dir: str | None = None,
    pollutants: list[str] | None = None,
) -> Path:
    """
    Main ingestion function. Pulls recent measurements and writes to Parquet.

    Args:
        lookback_hours: How many hours back to fetch (default 24).
        output_dir: Where to write Parquet files. Defaults to RAW_DATA_DIR.
        pollutants: Which pollutants to pull. Defaults to PM10, PM2.5, NO2, O3.

    Returns:
        Path to the written Parquet file.
    """
    if pollutants is None:
        pollutants = ["PM10", "PM2.5", "NO2", "O3"]

    if output_dir is None:
        output_dir = settings.raw_data_dir

    output_path = Path(output_dir) / "irceline"
    output_path.mkdir(parents=True, exist_ok=True)

    end = datetime.utcnow()
    start = end - timedelta(hours=lookback_hours)
    ingested_at = datetime.utcnow()

    # Match by label text
    label_map = {
        "PM10": "Particulate Matter < 10",
        "PM2.5": "Particulate Matter < 2.5",
        "NO2": "Nitrogen dioxide",
        "O3": "Ozone",
        "SO2": "Sulphur dioxide",
        "CO": "Carbon monoxide",
        "BC": "Black Carbon",
    }
    target_labels = [label_map[p] for p in pollutants if p in label_map]

    rows = []

    with httpx.Client(timeout=30) as client:
        # Get all timeseries metadata (station + pollutant combos)
        all_timeseries = fetch_timeseries_metadata(client)

        # Filter to our target pollutants
        relevant = [
            ts for ts in all_timeseries
            if any(
                target in ts.get("parameters", {}).get("phenomenon", {}).get("label", "")
                for target in target_labels
            )
        ]
        logger.info(
            f"Found {len(relevant)} timeseries for pollutants: {pollutants}"
        )

        for ts in relevant:
            ts_id = ts["id"]
            station = ts.get("station", {})
            phenomenon = ts.get("parameters", {}).get("phenomenon", {})
            unit = ts.get("uom", "µg/m³")

            # Extract station coordinates
            coords = station.get("geometry", {}).get("coordinates", [None, None])
            lon, lat = coords[0], coords[1]

            try:
                values = fetch_timeseries_data(client, ts_id, start, end)
            except Exception as e:
                logger.warning(f"Failed to fetch timeseries {ts_id}: {e}")
                continue

            for entry in values:
                rows.append(
                    {
                        "station_id": str(station.get("properties", {}).get("id", "")),
                        "station_label": station.get("properties", {}).get("label", ""),
                        "latitude": lat,
                        "longitude": lon,
                        "pollutant": phenomenon.get("label", ""),
                        "timestamp": datetime.fromtimestamp(entry["timestamp"] / 1000),
                        "value": entry.get("value"),
                        "unit": unit,
                        "ingested_at": ingested_at,
                    }
                )

    if not rows:
        logger.warning("No IRCELINE data fetched — check API or date range")
        table = pa.table({f.name: pa.array([], type=f.type) for f in IRCELINE_SCHEMA})
    else:
        table = pa.Table.from_pylist(rows, schema=IRCELINE_SCHEMA)

    # Partition by date for efficient reads
    date_str = end.strftime("%Y-%m-%d")
    file_path = output_path / f"irceline_{date_str}.parquet"
    pq.write_table(table, file_path)

    logger.info(f"Wrote {len(rows)} IRCELINE records to {file_path}")
    return file_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = ingest_irceline()
    print(f"Done: {path}")