"""
Open-Meteo API client.

Fetches weather data for Belgian station coordinates to enable
correlation analysis between meteorological conditions and air quality.
No API key required.

Docs: https://open-meteo.com/en/docs
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from tenacity import retry, stop_after_attempt, wait_exponential

from src.ingestion.config import settings

logger = logging.getLogger(__name__)

# Key Belgian cities/areas to fetch weather for.
# These cover the main regions where IRCELINE stations are clustered.
WEATHER_POINTS = [
    {"name": "Brussels", "lat": 50.85, "lon": 4.35},
    {"name": "Antwerp", "lat": 51.22, "lon": 4.40},
    {"name": "Ghent", "lat": 51.05, "lon": 3.72},
    {"name": "Liege", "lat": 50.63, "lon": 5.57},
    {"name": "Charleroi", "lat": 50.41, "lon": 4.44},
    {"name": "Bruges", "lat": 51.21, "lon": 3.22},
    {"name": "Namur", "lat": 50.47, "lon": 4.87},
    {"name": "Hasselt", "lat": 50.93, "lon": 5.34},
]

# Hourly variables relevant to air quality dispersion
HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "boundary_layer_height",  # Key for pollution trapping
]

WEATHER_SCHEMA = pa.schema(
    [
        pa.field("location_name", pa.string()),
        pa.field("latitude", pa.float64()),
        pa.field("longitude", pa.float64()),
        pa.field("timestamp", pa.timestamp("s")),
        pa.field("temperature_2m", pa.float64()),
        pa.field("relative_humidity_2m", pa.float64()),
        pa.field("wind_speed_10m", pa.float64()),
        pa.field("wind_direction_10m", pa.float64()),
        pa.field("precipitation", pa.float64()),
        pa.field("pressure_msl", pa.float64()),
        pa.field("cloud_cover", pa.float64()),
        pa.field("boundary_layer_height", pa.float64()),
        pa.field("ingested_at", pa.timestamp("ms")),
    ]
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
def _fetch_weather(
    client: httpx.Client,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> dict:
    """Fetch hourly weather data for a single coordinate."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }
    response = client.get(settings.open_meteo_url, params=params)
    response.raise_for_status()
    return response.json()


def ingest_weather(
    lookback_days: int = 1,
    output_dir: str | None = None,
    locations: list[dict] | None = None,
) -> Path:
    """
    Fetch weather data for Belgian locations and write to Parquet.

    Args:
        lookback_days: How many days back to fetch.
        output_dir: Output directory. Defaults to RAW_DATA_DIR.
        locations: Custom locations list. Defaults to WEATHER_POINTS.

    Returns:
        Path to written Parquet file.
    """
    if locations is None:
        locations = WEATHER_POINTS

    if output_dir is None:
        output_dir = settings.raw_data_dir

    output_path = Path(output_dir) / "weather"
    output_path.mkdir(parents=True, exist_ok=True)

    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)
    ingested_at = datetime.utcnow()

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    rows = []

    with httpx.Client(timeout=30) as client:
        for loc in locations:
            try:
                data = _fetch_weather(
                    client, loc["lat"], loc["lon"], start_str, end_str
                )
            except Exception as e:
                logger.warning(f"Failed weather fetch for {loc['name']}: {e}")
                continue

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])

            for i, t in enumerate(times):
                row = {
                    "location_name": loc["name"],
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "timestamp": datetime.fromisoformat(t),
                    "ingested_at": ingested_at,
                }
                for var in HOURLY_VARS:
                    values = hourly.get(var, [])
                    row[var] = values[i] if i < len(values) else None

                rows.append(row)

    if not rows:
        logger.warning("No weather data fetched")
        table = pa.table({f.name: pa.array([], type=f.type) for f in WEATHER_SCHEMA})
    else:
        table = pa.Table.from_pylist(rows, schema=WEATHER_SCHEMA)

    date_str = end.strftime("%Y-%m-%d")
    file_path = output_path / f"weather_{date_str}.parquet"
    pq.write_table(table, file_path)

    logger.info(f"Wrote {len(rows)} weather records to {file_path}")
    return file_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = ingest_weather()
    print(f"Done: {path}")
