"""
Shared configuration loaded from .env file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # API endpoints
    irceline_sos_url: str = field(
        default_factory=lambda: os.getenv(
            "IRCELINE_SOS_URL", "https://geo.irceline.be/sos/api/v1"
        )
    )
    openaq_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAQ_API_KEY", "")
    )
    open_meteo_url: str = field(
        default_factory=lambda: os.getenv(
            "OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
        )
    )

    # Storage paths
    raw_data_dir: str = field(
        default_factory=lambda: os.getenv("RAW_DATA_DIR", "./data/raw")
    )
    warehouse_path: str = field(
        default_factory=lambda: os.getenv(
            "WAREHOUSE_PATH", "./data/warehouse/air_quality.duckdb"
        )
    )

    def __post_init__(self):
        """Create directories if they don't exist."""
        Path(self.raw_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.warehouse_path).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()