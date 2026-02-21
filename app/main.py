"""
Madrid Housing Market Portal — application entry point.

Starts:
  - FastAPI (ASGI) with REST API routes at /api/v1/
  - Plotly Dash dashboard mounted at /dashboard/ (via WSGIMiddleware)
  - APScheduler background jobs
  - SQLAlchemy database initialisation + demo data seeding
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.database import init_db
from app.api.routes import router as api_router
from app.dashboard.layout import create_layout
from app.dashboard.callbacks import register_callbacks
from app.scheduler import start_scheduler, stop_scheduler


# ── Logging setup ──────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)
logger.add(
    settings.log_file,
    rotation="10 MB",
    retention="30 days",
    level=settings.log_level,
    enqueue=True,
)


# ── Dash application ───────────────────────────────────────────────────────────

def create_dash_app() -> dash.Dash:
    """Instantiate and configure the Plotly Dash app."""
    dash_app = dash.Dash(
        __name__,
        server=True,  # Use Dash's own Flask server
        routes_pathname_prefix="/",
        requests_pathname_prefix="/dashboard/",
        external_stylesheets=[
            dbc.themes.SLATE,
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        ],
        title="Madrid Housing Portal",
        suppress_callback_exceptions=True,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
            {"name": "description", "content": "Madrid Housing Market Analytics Portal"},
        ],
    )

    # Custom CSS for dark dropdown menus and tab styling
    dash_app.index_string = _custom_index_string()
    dash_app.layout = create_layout()
    register_callbacks(dash_app)
    return dash_app


def _custom_index_string() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
        body { background-color: #0d1117 !important; }
        .Select-control, .Select-menu-outer {
            background-color: #161b22 !important;
            border-color: #30363d !important;
            color: #E6EDF3 !important;
        }
        .Select-value-label, .Select-placeholder { color: #E6EDF3 !important; }
        .Select-option { background-color: #161b22 !important; color: #E6EDF3 !important; }
        .Select-option:hover { background-color: #21262d !important; }
        .VirtualizedSelectOption { background-color: #161b22 !important; }
        .nav-tabs { border-bottom: 2px solid #30363d !important; }
        .nav-tabs .nav-link { color: #8B949E !important; border: none !important; padding: 10px 16px; }
        .nav-tabs .nav-link.active {
            color: #4FC3F7 !important;
            background: transparent !important;
            border-bottom: 2px solid #4FC3F7 !important;
        }
        .nav-tabs .nav-link:hover { color: #E6EDF3 !important; }
        .rc-slider-rail { background-color: #30363d !important; }
        .rc-slider-track { background-color: #4FC3F7 !important; }
        .rc-slider-handle { border-color: #4FC3F7 !important; background-color: #4FC3F7 !important; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0d1117; }
        ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #8B949E; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>
"""


# ── FastAPI lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("Starting Madrid Housing Market Portal …")

    # Initialise DB (create tables)
    init_db()
    logger.info("Database initialised.")

    # Seed demo data if DB is empty
    from app.database import SessionLocal
    from app.models.housing import District
    with SessionLocal() as db:
        count = db.query(District).count()

    if count == 0:
        logger.info("Empty database detected — seeding demo data …")
        from app.data.pipeline import DataPipeline
        p = DataPipeline()
        p.ensure_districts()
        p.seed_demo_data()

        from app.services.forecasting import ForecastingService
        ForecastingService().forecast_all_districts(periods=8)
        logger.info("Demo data and forecasts ready.")

    # Try to download GeoJSON for map visualisation
    try:
        from app.data.pipeline import DataPipeline
        DataPipeline().download_districts_geojson()
    except Exception:
        pass

    # Start background scheduler
    start_scheduler()

    yield  # Application is running

    # ── Shutdown ───────────────────────────────────────────────────────────────
    stop_scheduler()
    logger.info("Portal shut down cleanly.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Madrid Housing Market API",
    description=(
        "REST API for Madrid housing market data: "
        "price trends, forecasts, rental analysis, and mortgage statistics."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# REST API routes
app.include_router(api_router)

# Static files
static_path = Path("static")
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Health check
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "Madrid Housing Portal"}

# Root redirect → dashboard
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard/")

# Mount Dash at /dashboard (WSGI inside ASGI via Starlette middleware)
dash_app = create_dash_app()
app.mount("/dashboard", WSGIMiddleware(dash_app.server))


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
    )
