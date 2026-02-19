#!/usr/bin/env python3
"""
Quick-start script.  Run with:

    python run.py              # development (hot-reload)
    python run.py --prod       # production (no reload)
    python run.py --seed-only  # only seed data, no server

Requirements: install dependencies first with:
    pip install -r requirements.txt
"""

import argparse
import sys

from pathlib import Path

# Ensure the project root is on the Python path
sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Madrid Housing Market Portal")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--prod", action="store_true", help="Production mode (no reload)")
    parser.add_argument("--seed-only", action="store_true", help="Seed data and exit")
    args = parser.parse_args()

    if args.seed_only:
        print("Seeding demo data …")
        from app.database import init_db
        from app.data.pipeline import DataPipeline
        from app.services.forecasting import ForecastingService
        init_db()
        p = DataPipeline()
        p.ensure_districts()
        p.seed_demo_data()
        ForecastingService().forecast_all_districts(periods=8)
        print("Done. You can now start the portal with: python run.py")
        return

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,
        log_level="info",
    )


if __name__ == "__main__":
    main()
