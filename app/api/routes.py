"""FastAPI REST API routes for the Madrid Housing Market Portal."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger

from app.api.schemas import (
    AffordabilitySchema,
    DataRefreshResponse,
    DistrictSchema,
    DistrictSnapshotSchema,
    HousingPriceIndexSchema,
    MarketSummarySchema,
    MortgageDataSchema,
    PriceForecastSchema,
    RentalAnalysisSchema,
)
from app.data.pipeline import DataPipeline
from app.database import SessionLocal, get_db
from app.models.housing import District
from app.services.analytics import AnalyticsService
from app.services.forecasting import ForecastingService

router = APIRouter(prefix="/api/v1", tags=["Housing Market Data"])

# Singleton services (stateless — safe to share)
analytics = AnalyticsService()
forecasting = ForecastingService()
pipeline = DataPipeline()


# ── Districts ──────────────────────────────────────────────────────────────────

@router.get("/districts", response_model=list[DistrictSchema])
def list_districts(db=Depends(get_db)):
    """List all 21 Madrid administrative districts."""
    return db.query(District).order_by(District.code).all()


@router.get("/districts/{code}", response_model=DistrictSchema)
def get_district(code: str, db=Depends(get_db)):
    """Return a single district by its two-digit code (e.g. '04' for Salamanca)."""
    district = db.query(District).filter_by(code=code).first()
    if not district:
        raise HTTPException(status_code=404, detail=f"District '{code}' not found.")
    return district


# ── Market summary ─────────────────────────────────────────────────────────────

@router.get("/summary", response_model=MarketSummarySchema)
def market_summary():
    """High-level KPI snapshot for the current period."""
    summary = analytics.get_market_summary()
    if not summary:
        raise HTTPException(status_code=503, detail="No market data available.")
    return summary


# ── Price trends ───────────────────────────────────────────────────────────────

@router.get("/prices/trends")
def price_trends(
    district: str | None = Query(None, description="District code (e.g. '04')"),
    property_type: str = Query("all", enum=["all", "new", "second_hand"]),
    from_year: int = Query(2019, ge=2000, le=2030),
):
    """Quarterly sale-price trend, optionally filtered by district and property type."""
    return analytics.get_price_trends(
        district_code=district,
        property_type=property_type,
        from_year=from_year,
    )


@router.get("/prices/snapshot", response_model=list[DistrictSnapshotSchema])
def price_snapshot(
    year: int | None = Query(None),
    quarter: int | None = Query(None, ge=1, le=4),
):
    """Current price per m² for all districts in a given period."""
    return analytics.get_district_snapshot(year, quarter)


# ── Rental market ──────────────────────────────────────────────────────────────

@router.get("/rental/analysis", response_model=list[RentalAnalysisSchema])
def rental_analysis(
    year: int | None = Query(None),
    quarter: int | None = Query(None, ge=1, le=4),
):
    """Rental prices and gross yields per district."""
    return analytics.get_rental_analysis(year, quarter)


# ── IPV (Housing Price Index) ──────────────────────────────────────────────────

@router.get("/ipv", response_model=list[HousingPriceIndexSchema])
def housing_price_index(
    property_type: str = Query("all", enum=["all", "new", "second_hand"]),
    from_year: int = Query(2019, ge=2000, le=2030),
):
    """INE Housing Price Index (Índice de Precios de Vivienda) for Madrid."""
    return analytics.get_ipv_trends(property_type=property_type, from_year=from_year)


# ── Mortgages ──────────────────────────────────────────────────────────────────

@router.get("/mortgages", response_model=list[MortgageDataSchema])
def mortgage_trends(from_year: int = Query(2019, ge=2000, le=2030)):
    """Monthly mortgage statistics for Madrid."""
    return analytics.get_mortgage_trends(from_year=from_year)


# ── Forecasting ────────────────────────────────────────────────────────────────

@router.get("/forecast/{district_code}", response_model=list[PriceForecastSchema])
def forecast_district(
    district_code: str,
    periods: int = Query(8, ge=1, le=20, description="Quarters ahead to forecast"),
    model: str = Query("ensemble", enum=["ensemble", "sarima", "linear"]),
):
    """
    Generate (or retrieve cached) price forecast for a district.

    Forecasts are computed on first call and stored for subsequent requests.
    """
    stored = forecasting.get_stored_forecasts(
        district_code=district_code, model_name=model
    )
    if stored:
        return stored
    # Generate and store
    rows = forecasting.forecast_district(district_code, periods=periods)
    return rows


@router.post("/forecast/run-all", response_model=DataRefreshResponse)
def run_all_forecasts(
    background_tasks: BackgroundTasks,
    periods: int = Query(8, ge=1, le=20),
):
    """Trigger forecast generation for all districts (runs in background)."""
    background_tasks.add_task(forecasting.forecast_all_districts, periods)
    return DataRefreshResponse(
        status="accepted",
        message=f"Forecast generation for all districts queued ({periods} periods).",
    )


# ── Affordability ──────────────────────────────────────────────────────────────

@router.get("/affordability", response_model=AffordabilitySchema)
def affordability():
    """Affordability metrics for a typical 80 m² apartment in Madrid."""
    data = analytics.get_affordability_metrics()
    if not data:
        raise HTTPException(status_code=503, detail="No data available.")
    return data


# ── Data management ────────────────────────────────────────────────────────────

@router.post("/data/refresh", response_model=DataRefreshResponse)
def refresh_data(background_tasks: BackgroundTasks):
    """Trigger a full data refresh from all configured sources (background)."""
    background_tasks.add_task(pipeline.run_full_update)
    return DataRefreshResponse(
        status="accepted",
        message="Full data refresh queued.",
    )


@router.post("/data/seed", response_model=DataRefreshResponse)
def seed_demo_data():
    """(Re-)seed the database with synthetic demo data."""
    try:
        pipeline.ensure_districts()
        pipeline.seed_demo_data()
        return DataRefreshResponse(
            status="success", message="Demo data seeded successfully."
        )
    except Exception as exc:
        logger.error(f"Seed failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
