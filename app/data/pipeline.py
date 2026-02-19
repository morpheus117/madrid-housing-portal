"""
Data pipeline: orchestrates fetching from all sources, transforming data,
persisting to the database, and seeding demo data when live APIs are unavailable.
"""

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.data.catastro_client import CatastroClient
from app.data.idealista_client import IdealistaClient
from app.data.ine_client import INEClient
from app.database import db_session
from app.models.housing import (
    DataFetchLog,
    District,
    HousingPriceIndex,
    MortgageData,
    RentalPrice,
    SalePrice,
)


# ── Madrid district reference data ─────────────────────────────────────────────
MADRID_DISTRICTS: list[dict] = [
    {"code": "01", "name": "Centro",               "name_es": "Centro",               "lat": 40.4153, "lon": -3.7074, "area_km2": 5.23},
    {"code": "02", "name": "Arganzuela",            "name_es": "Arganzuela",            "lat": 40.3964, "lon": -3.7014, "area_km2": 6.77},
    {"code": "03", "name": "Retiro",                "name_es": "Retiro",                "lat": 40.4083, "lon": -3.6822, "area_km2": 5.46},
    {"code": "04", "name": "Salamanca",             "name_es": "Salamanca",             "lat": 40.4296, "lon": -3.6764, "area_km2": 5.22},
    {"code": "05", "name": "Chamartín",             "name_es": "Chamartín",             "lat": 40.4575, "lon": -3.6806, "area_km2": 8.63},
    {"code": "06", "name": "Tetuán",                "name_es": "Tetuán",                "lat": 40.4607, "lon": -3.7022, "area_km2": 5.36},
    {"code": "07", "name": "Chamberí",              "name_es": "Chamberí",              "lat": 40.4371, "lon": -3.7036, "area_km2": 4.68},
    {"code": "08", "name": "Fuencarral-El Pardo",   "name_es": "Fuencarral-El Pardo",   "lat": 40.4902, "lon": -3.7169, "area_km2": 235.87},
    {"code": "09", "name": "Moncloa-Aravaca",       "name_es": "Moncloa-Aravaca",       "lat": 40.4348, "lon": -3.7308, "area_km2": 49.70},
    {"code": "10", "name": "Latina",                "name_es": "Latina",                "lat": 40.3938, "lon": -3.7385, "area_km2": 25.42},
    {"code": "11", "name": "Carabanchel",           "name_es": "Carabanchel",           "lat": 40.3735, "lon": -3.7374, "area_km2": 21.00},
    {"code": "12", "name": "Usera",                 "name_es": "Usera",                 "lat": 40.3863, "lon": -3.7129, "area_km2": 7.72},
    {"code": "13", "name": "Puente de Vallecas",    "name_es": "Puente de Vallecas",    "lat": 40.3868, "lon": -3.6786, "area_km2": 14.77},
    {"code": "14", "name": "Moratalaz",             "name_es": "Moratalaz",             "lat": 40.4061, "lon": -3.6467, "area_km2": 7.15},
    {"code": "15", "name": "Ciudad Lineal",         "name_es": "Ciudad Lineal",         "lat": 40.4413, "lon": -3.6578, "area_km2": 11.79},
    {"code": "16", "name": "Hortaleza",             "name_es": "Hortaleza",             "lat": 40.4753, "lon": -3.6364, "area_km2": 27.32},
    {"code": "17", "name": "Villaverde",            "name_es": "Villaverde",            "lat": 40.3474, "lon": -3.7092, "area_km2": 23.42},
    {"code": "18", "name": "Villa de Vallecas",     "name_es": "Villa de Vallecas",     "lat": 40.3640, "lon": -3.6153, "area_km2": 55.30},
    {"code": "19", "name": "Vicálvaro",             "name_es": "Vicálvaro",             "lat": 40.4036, "lon": -3.6089, "area_km2": 58.05},
    {"code": "20", "name": "San Blas-Canillejas",   "name_es": "San Blas-Canillejas",   "lat": 40.4283, "lon": -3.6239, "area_km2": 16.80},
    {"code": "21", "name": "Barajas",               "name_es": "Barajas",               "lat": 40.4762, "lon": -3.5787, "area_km2": 44.20},
]

# Price multiplier relative to city average (1.0 = city average)
DISTRICT_PRICE_MULTIPLIER: dict[str, float] = {
    "01": 1.25, "02": 1.00, "03": 1.25, "04": 1.40,
    "05": 1.20, "06": 0.95, "07": 1.30, "08": 1.05,
    "09": 1.15, "10": 0.85, "11": 0.75, "12": 0.70,
    "13": 0.65, "14": 0.75, "15": 0.95, "16": 0.95,
    "17": 0.60, "18": 0.65, "19": 0.65, "20": 0.75,
    "21": 0.85,
}

# City-wide average sale price per m² by quarter (2019 Q1 → 2025 Q4)
CITY_AVG_PRICE_SERIES: dict[tuple[int, int], float] = {
    (2019, 1): 3520, (2019, 2): 3580, (2019, 3): 3640, (2019, 4): 3680,
    (2020, 1): 3700, (2020, 2): 3550, (2020, 3): 3580, (2020, 4): 3620,
    (2021, 1): 3680, (2021, 2): 3760, (2021, 3): 3840, (2021, 4): 3920,
    (2022, 1): 4020, (2022, 2): 4140, (2022, 3): 4220, (2022, 4): 4280,
    (2023, 1): 4340, (2023, 2): 4400, (2023, 3): 4460, (2023, 4): 4520,
    (2024, 1): 4600, (2024, 2): 4680, (2024, 3): 4760, (2024, 4): 4820,
    (2025, 1): 4900, (2025, 2): 4960, (2025, 3): 5020, (2025, 4): 5080,
}

# Rental price per m²/month multiplier vs sale (approx gross yield target)
RENTAL_SALE_RATIO = 0.003  # ~3 €/m²·month per 1000 €/m² sale price


class DataPipeline:
    """Orchestrates all data-fetch operations and database persistence."""

    def __init__(self) -> None:
        self.ine = INEClient()
        self.catastro = CatastroClient()
        self.idealista = IdealistaClient()

    # ── Top-level orchestration ────────────────────────────────────────────────

    def run_full_update(self) -> dict[str, Any]:
        """Fetch all sources and update the database.  Returns a status dict."""
        logger.info("Starting full data update …")
        results: dict[str, Any] = {}

        results["districts"] = self.ensure_districts()
        results["ine_ipv"] = self.update_ine_ipv()
        results["ine_mortgages"] = self.update_ine_mortgages()
        results["geojson"] = self.download_districts_geojson()

        logger.info(f"Full update complete: {results}")
        return results

    def seed_demo_data(self) -> None:
        """Populate the database with realistic synthetic data for demo use."""
        logger.info("Seeding demo data …")
        with db_session() as db:
            self._seed_districts(db)
            self._seed_sale_prices(db)
            self._seed_rental_prices(db)
            self._seed_ipv(db)
            self._seed_mortgages(db)
        logger.info("Demo data seeded successfully.")

    # ── District management ────────────────────────────────────────────────────

    def ensure_districts(self) -> int:
        """Upsert the 21 Madrid districts.  Returns count inserted/updated."""
        count = 0
        with db_session() as db:
            for d in MADRID_DISTRICTS:
                existing = db.query(District).filter_by(code=d["code"]).first()
                if existing is None:
                    db.add(
                        District(
                            code=d["code"],
                            name=d["name"],
                            name_es=d["name_es"],
                            latitude=d["lat"],
                            longitude=d["lon"],
                            area_km2=d["area_km2"],
                        )
                    )
                    count += 1
        logger.info(f"Districts ensured: {count} new records.")
        return count

    # ── INE IPV ────────────────────────────────────────────────────────────────

    def update_ine_ipv(self) -> int:
        """Fetch IPV from INE and upsert into the database."""
        started = datetime.utcnow()
        records = 0
        status = "success"
        error_msg = None
        try:
            rows = self.ine.get_housing_price_index(n_periods=24)
            if not rows:
                logger.warning("INE IPV returned no data — skipping.")
                status = "skipped"
            else:
                with db_session() as db:
                    for row in rows:
                        self._upsert_ipv(db, row)
                        records += 1
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            logger.error(f"INE IPV update failed: {exc}")
        finally:
            self._log_fetch(
                "INE", "IPV", status, records, error_msg, started
            )
        return records

    def update_ine_mortgages(self) -> int:
        """Fetch mortgage stats from INE and upsert into the database."""
        started = datetime.utcnow()
        records = 0
        status = "success"
        error_msg = None
        try:
            rows = self.ine.get_mortgage_stats(n_periods=36)
            if not rows:
                logger.warning("INE Mortgages returned no data — skipping.")
                status = "skipped"
            else:
                with db_session() as db:
                    for row in rows:
                        self._upsert_mortgage(db, row)
                        records += 1
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            logger.error(f"INE Mortgage update failed: {exc}")
        finally:
            self._log_fetch(
                "INE", "EH_Hipotecas", status, records, error_msg, started
            )
        return records

    # ── GeoJSON ────────────────────────────────────────────────────────────────

    def download_districts_geojson(self) -> bool:
        """
        Download the Madrid districts GeoJSON from the Open Data portal.
        Saves to the path specified by settings.geojson_cache_path.
        Returns True on success.
        """
        cache_path = Path(settings.geojson_cache_path)
        if cache_path.exists():
            logger.info("Districts GeoJSON already cached — skipping download.")
            return True

        url = (
            "https://datos.madrid.es/egob/catalogo/200078-0-distritos.geojson"
        )
        logger.info(f"Downloading districts GeoJSON from {url} …")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(resp.content)
            logger.info(f"GeoJSON saved to {cache_path}")
            return True
        except Exception as exc:
            logger.warning(
                f"Could not download districts GeoJSON: {exc}. "
                "Map visualisation will use point markers as fallback."
            )
            return False

    # ── Seed helpers ───────────────────────────────────────────────────────────

    def _seed_districts(self, db: Session) -> None:
        for d in MADRID_DISTRICTS:
            if not db.query(District).filter_by(code=d["code"]).first():
                db.add(
                    District(
                        code=d["code"],
                        name=d["name"],
                        name_es=d["name_es"],
                        latitude=d["lat"],
                        longitude=d["lon"],
                        area_km2=d["area_km2"],
                    )
                )
        db.flush()

    def _seed_sale_prices(self, db: Session) -> None:
        districts = {d.code: d for d in db.query(District).all()}
        random.seed(42)
        for (year, quarter), city_avg in CITY_AVG_PRICE_SERIES.items():
            for code, district in districts.items():
                multiplier = DISTRICT_PRICE_MULTIPLIER.get(code, 1.0)
                noise = random.gauss(0, city_avg * 0.01)
                price = round(city_avg * multiplier + noise, 2)
                # New vs second-hand split
                for ptype, factor in [("all", 1.0), ("new", 1.18), ("second_hand", 0.96)]:
                    if not db.query(SalePrice).filter_by(
                        district_id=district.id, year=year,
                        quarter=quarter, property_type=ptype,
                    ).first():
                        db.add(
                            SalePrice(
                                district_id=district.id,
                                year=year,
                                quarter=quarter,
                                price_per_m2=round(price * factor, 2),
                                property_type=ptype,
                                transactions=random.randint(80, 600),
                                source="demo",
                            )
                        )

    def _seed_rental_prices(self, db: Session) -> None:
        districts = {d.code: d for d in db.query(District).all()}
        random.seed(99)
        for (year, quarter), city_avg in CITY_AVG_PRICE_SERIES.items():
            for code, district in districts.items():
                multiplier = DISTRICT_PRICE_MULTIPLIER.get(code, 1.0)
                rental = round(city_avg * multiplier * RENTAL_SALE_RATIO, 2)
                noise = random.gauss(0, rental * 0.05)
                if not db.query(RentalPrice).filter_by(
                    district_id=district.id, year=year, quarter=quarter
                ).first():
                    db.add(
                        RentalPrice(
                            district_id=district.id,
                            year=year,
                            quarter=quarter,
                            price_per_m2_month=round(rental + noise, 2),
                            listings_count=random.randint(50, 400),
                            source="demo",
                        )
                    )

    def _seed_ipv(self, db: Session) -> None:
        base_index = 100.0
        prev_index: dict[str, float] = {t: base_index for t in ("all", "new", "second_hand")}
        period_list = sorted(CITY_AVG_PRICE_SERIES.keys())
        for i, (year, quarter) in enumerate(period_list):
            city_avg = CITY_AVG_PRICE_SERIES[(year, quarter)]
            for ptype, growth_factor in [("all", 1.0), ("new", 1.02), ("second_hand", 0.99)]:
                if i == 0:
                    index = base_index
                else:
                    prev_avg = CITY_AVG_PRICE_SERIES[period_list[i - 1]]
                    qoq = (city_avg - prev_avg) / prev_avg
                    index = prev_index[ptype] * (1 + qoq) * growth_factor

                yoy = None
                if i >= 4:
                    yoy = (index / prev_index[ptype] - 1) * 100 if i >= 4 else None
                    # compute proper yoy
                    yoy_period = period_list[i - 4]
                    # approximate
                    prev_year_avg = CITY_AVG_PRICE_SERIES.get(yoy_period)
                    if prev_year_avg:
                        yoy = round((city_avg - prev_year_avg) / prev_year_avg * 100, 2)

                qoq_pct = None
                if i > 0:
                    prev_avg = CITY_AVG_PRICE_SERIES[period_list[i - 1]]
                    qoq_pct = round((city_avg - prev_avg) / prev_avg * 100, 2)

                if not db.query(HousingPriceIndex).filter_by(
                    year=year, quarter=quarter, property_type=ptype
                ).first():
                    db.add(
                        HousingPriceIndex(
                            year=year,
                            quarter=quarter,
                            property_type=ptype,
                            index_value=round(index, 2),
                            annual_variation_pct=yoy,
                            quarterly_variation_pct=qoq_pct,
                            source="demo",
                        )
                    )
                prev_index[ptype] = index

    def _seed_mortgages(self, db: Session) -> None:
        random.seed(77)
        for year in range(2019, 2026):
            for month in range(1, 13):
                if year == 2025 and month > 9:
                    break  # only up to Q3 2025
                base_mortgages = 6000 + (year - 2019) * 200
                if year == 2020 and month in (4, 5, 6):
                    base_mortgages = int(base_mortgages * 0.5)  # COVID drop
                noise = random.randint(-400, 400)
                if not db.query(MortgageData).filter_by(year=year, month=month).first():
                    rate = 1.5 + (year - 2019) * 0.3 + random.gauss(0, 0.1)
                    db.add(
                        MortgageData(
                            year=year,
                            month=month,
                            num_mortgages=max(1000, base_mortgages + noise),
                            avg_amount_eur=round(230000 + (year - 2019) * 8000 + random.gauss(0, 5000), 0),
                            avg_interest_rate=round(max(0.5, rate), 2),
                            fixed_rate_pct=round(min(90, 45 + (year - 2019) * 5 + random.gauss(0, 3)), 1),
                            avg_duration_years=round(24 + random.gauss(0, 1), 1),
                            source="demo",
                        )
                    )

    # ── DB upsert helpers ──────────────────────────────────────────────────────

    def _upsert_ipv(self, db: Session, row: dict) -> None:
        existing = db.query(HousingPriceIndex).filter_by(
            year=row["year"],
            quarter=row["quarter"],
            property_type=row.get("property_type", "all"),
        ).first()
        if existing:
            existing.index_value = row["index_value"]
            existing.annual_variation_pct = row.get("annual_variation_pct")
            existing.quarterly_variation_pct = row.get("quarterly_variation_pct")
            existing.source = "INE"
        else:
            db.add(HousingPriceIndex(**row, source="INE"))

    def _upsert_mortgage(self, db: Session, row: dict) -> None:
        if "year" not in row or "month" not in row:
            return
        existing = db.query(MortgageData).filter_by(
            year=row["year"], month=row["month"]
        ).first()
        if existing:
            for k, v in row.items():
                setattr(existing, k, v)
            existing.source = "INE"
        else:
            db.add(MortgageData(**{**row, "source": "INE"}))

    # ── Audit log ──────────────────────────────────────────────────────────────

    def _log_fetch(
        self,
        source: str,
        endpoint: str,
        status: str,
        records: int,
        error_msg: str | None,
        started: datetime,
    ) -> None:
        with db_session() as db:
            db.add(
                DataFetchLog(
                    source=source,
                    endpoint=endpoint,
                    status=status,
                    records_fetched=records,
                    error_message=error_msg,
                    started_at=started,
                )
            )
