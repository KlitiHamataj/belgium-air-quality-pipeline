"""
Manual runner for all ingestion jobs.
Use this for local development or one-off backfills.
In production, Airflow handles scheduling.
"""

import logging
import sys
from datetime import datetime

from src.ingestion.irceline import ingest_irceline
from src.ingestion.weather import ingest_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def run_all(lookback_hours: int = 24):
    """Run all ingestion jobs sequentially."""
    start = datetime.utcnow()
    logger.info(f"Starting ingestion run (lookback={lookback_hours}h)")

    results = {}

    # 1. IRCELINE (primary source)
    try:
        path = ingest_irceline(lookback_hours=lookback_hours)
        results["irceline"] = {"status": "success", "path": str(path)}
    except Exception as e:
        logger.error(f"IRCELINE ingestion failed: {e}")
        results["irceline"] = {"status": "failed", "error": str(e)}

    # 2. Weather (enrichment)
    try:
        lookback_days = max(1, lookback_hours // 24)
        path = ingest_weather(lookback_days=lookback_days)
        results["weather"] = {"status": "success", "path": str(path)}
    except Exception as e:
        logger.error(f"Weather ingestion failed: {e}")
        results["weather"] = {"status": "failed", "error": str(e)}

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"Ingestion complete in {elapsed:.1f}s")

    for source, result in results.items():
        status = result["status"]
        detail = result.get("path", result.get("error", ""))
        logger.info(f"  {source}: {status} — {detail}")

    if any(r["status"] == "failed" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    run_all(lookback_hours=hours)