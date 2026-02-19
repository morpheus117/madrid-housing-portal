"""Tests for the ForecastingService."""

import pytest

from app.database import init_db
from app.data.pipeline import DataPipeline
from app.services.forecasting import ForecastingService


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    import os
    os.environ["DATABASE_URL"] = "sqlite:///./test_forecast.db"
    from importlib import reload
    import app.config as cfg
    reload(cfg)
    import app.database as db_module
    reload(db_module)
    init_db()
    p = DataPipeline()
    p.ensure_districts()
    p.seed_demo_data()
    yield
    from pathlib import Path
    Path("test_forecast.db").unlink(missing_ok=True)


def test_forecast_district():
    svc = ForecastingService()
    rows = svc.forecast_district("04", periods=4)
    assert len(rows) == 4
    for r in rows:
        assert r["predicted_price_m2"] > 0
        assert r["lower_bound"] <= r["predicted_price_m2"] <= r["upper_bound"]


def test_forecast_stored_retrieval():
    svc = ForecastingService()
    # Generate
    svc.forecast_district("01", periods=4)
    # Retrieve stored
    stored = svc.get_stored_forecasts(district_code="01", model_name="ensemble")
    assert len(stored) > 0


def test_forecast_confidence_bounds():
    svc = ForecastingService()
    rows = svc.forecast_district("07", periods=4)
    for r in rows:
        assert r["confidence_level"] == pytest.approx(0.95, rel=0.01)
