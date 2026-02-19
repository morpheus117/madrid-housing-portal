"""Tests for the AnalyticsService."""

import pytest

from app.config import settings
from app.database import init_db
from app.data.pipeline import DataPipeline
from app.services.analytics import AnalyticsService


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create tables and seed demo data once for all tests in this module."""
    # Use a fresh in-memory SQLite for testing
    import os
    os.environ["DATABASE_URL"] = "sqlite:///./test_housing.db"
    # Re-import so the new env var is picked up
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
    # Cleanup
    from pathlib import Path
    Path("test_housing.db").unlink(missing_ok=True)


def test_market_summary():
    svc = AnalyticsService()
    summary = svc.get_market_summary()
    assert summary, "Market summary should not be empty"
    assert "avg_sale_price_m2" in summary
    assert summary["avg_sale_price_m2"] > 0


def test_district_snapshot():
    svc = AnalyticsService()
    snap = svc.get_district_snapshot()
    assert len(snap) == 21, "Should return all 21 districts"
    for d in snap:
        assert "price_per_m2" in d
        assert d["price_per_m2"] > 0


def test_price_trends_city():
    svc = AnalyticsService()
    trends = svc.get_price_trends(from_year=2022)
    assert len(trends) > 0
    for t in trends:
        assert "price_per_m2" in t
        assert t["price_per_m2"] > 0


def test_price_trends_district():
    svc = AnalyticsService()
    trends = svc.get_price_trends(district_code="04", property_type="all", from_year=2022)
    assert len(trends) > 0


def test_rental_analysis():
    svc = AnalyticsService()
    rental = svc.get_rental_analysis()
    assert len(rental) > 0
    for r in rental:
        assert r["rental_price_m2_month"] > 0
        assert r["gross_yield_pct"] is not None


def test_mortgage_trends():
    svc = AnalyticsService()
    mortgages = svc.get_mortgage_trends(from_year=2020)
    assert len(mortgages) > 0


def test_affordability_metrics():
    svc = AnalyticsService()
    aff = svc.get_affordability_metrics()
    assert "mortgage_to_income_pct" in aff
    assert aff["years_of_income_to_buy"] > 0


def test_ipv_trends():
    svc = AnalyticsService()
    ipv = svc.get_ipv_trends(from_year=2020)
    assert len(ipv) > 0
