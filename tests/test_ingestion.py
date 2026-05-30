"""Unit tests for ingestion modules."""

import pytest


def test_irceline_schema_fields():
    from src.ingestion.irceline import IRCELINE_SCHEMA
    field_names = {f.name for f in IRCELINE_SCHEMA}
    assert "station_id" in field_names
    assert "pollutant" in field_names
    assert "value" in field_names
    assert "timestamp" in field_names


def test_weather_points_cover_main_cities():
    from src.ingestion.weather import WEATHER_POINTS
    names = {p["name"] for p in WEATHER_POINTS}
    assert "Brussels" in names
    assert "Antwerp" in names
    assert "Ghent" in names
    assert "Liege" in names


def test_weather_points_have_valid_coords():
    from src.ingestion.weather import WEATHER_POINTS
    for point in WEATHER_POINTS:
        assert 49.5 <= point["lat"] <= 51.5, f"{point['name']} lat out of range"
        assert 2.5 <= point["lon"] <= 6.5, f"{point['name']} lon out of range"


def test_settings_defaults():
    from src.ingestion.config import Settings
    s = Settings()
    assert "irceline.be" in s.irceline_sos_url
    assert "open-meteo.com" in s.open_meteo_url