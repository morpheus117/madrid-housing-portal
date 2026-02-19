"""
Analytics service — computes statistics, trends, and market summaries
from the database for use in the API and dashboard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import db_session
from app.models.housing import (
    District,
    HousingPriceIndex,
    MortgageData,
    RentalPrice,
    SalePrice,
)


class AnalyticsService:
    """Compute analytical summaries and KPIs from stored housing data."""

    # Average Madrid household income (gross, approximate 2024)
    MADRID_AVG_INCOME_EUR = 35_000
    # Standard mortgage term assumptions
    MORTGAGE_LTV = 0.80
    MORTGAGE_YEARS = 25

    # ── Market summary ─────────────────────────────────────────────────────────

    def get_market_summary(self) -> dict[str, Any]:
        """Return high-level KPIs for the current period."""
        with db_session() as db:
            latest = self._latest_period(db, SalePrice)
            if not latest:
                return {}
            year, quarter = latest

            avg_price = self._city_avg_price(db, year, quarter)
            prev_year_price = self._city_avg_price(db, year - 1, quarter)
            avg_rental = self._city_avg_rental(db, year, quarter)
            mortgages = self._latest_mortgage_count(db, year)
            ipv = self._latest_ipv(db, year, quarter)

            yoy_pct = (
                round((avg_price - prev_year_price) / prev_year_price * 100, 2)
                if prev_year_price
                else None
            )
            gross_yield = (
                round(avg_rental * 12 / avg_price * 100, 2)
                if avg_price and avg_rental
                else None
            )
            years_to_buy = self._years_to_buy(avg_price)

            return {
                "period": f"{year} Q{quarter}",
                "avg_sale_price_m2": round(avg_price, 2) if avg_price else None,
                "yoy_price_change_pct": yoy_pct,
                "avg_rental_m2_month": round(avg_rental, 2) if avg_rental else None,
                "gross_rental_yield_pct": gross_yield,
                "annual_mortgages": mortgages,
                "ipv_annual_variation_pct": ipv.annual_variation_pct if ipv else None,
                "years_to_buy": years_to_buy,
                "affordability_index": self._affordability_index(avg_price),
            }

    # ── Price trends ──────────────────────────────────────────────────────────

    def get_price_trends(
        self,
        district_code: str | None = None,
        property_type: str = "all",
        from_year: int = 2019,
    ) -> list[dict]:
        """Return quarterly sale-price trend data."""
        with db_session() as db:
            query = db.query(SalePrice).filter(
                SalePrice.year >= from_year,
                SalePrice.property_type == property_type,
            )
            if district_code:
                district = db.query(District).filter_by(code=district_code).first()
                if district:
                    query = query.filter_by(district_id=district.id)
            rows = query.order_by(SalePrice.year, SalePrice.quarter).all()

            if district_code:
                return [
                    {
                        "year": r.year,
                        "quarter": r.quarter,
                        "period": r.period_label,
                        "price_per_m2": r.price_per_m2,
                        "transactions": r.transactions,
                        "district": district_code,
                    }
                    for r in rows
                ]

            # City-wide average across districts
            df = pd.DataFrame(
                [{"year": r.year, "quarter": r.quarter, "price": r.price_per_m2}
                 for r in rows]
            )
            if df.empty:
                return []
            agg = (
                df.groupby(["year", "quarter"])["price"]
                .mean()
                .reset_index()
                .rename(columns={"price": "price_per_m2"})
            )
            return [
                {
                    "year": int(row.year),
                    "quarter": int(row.quarter),
                    "period": f"{int(row.year)} Q{int(row.quarter)}",
                    "price_per_m2": round(float(row.price_per_m2), 2),
                    "district": "All Madrid",
                }
                for row in agg.itertuples()
            ]

    # ── District comparison ────────────────────────────────────────────────────

    def get_district_snapshot(self, year: int | None = None, quarter: int | None = None) -> list[dict]:
        """Return per-district price snapshot for a given period."""
        with db_session() as db:
            if year is None or quarter is None:
                latest = self._latest_period(db, SalePrice)
                if not latest:
                    return []
                year, quarter = latest

            rows = (
                db.query(SalePrice, District)
                .join(District, SalePrice.district_id == District.id)
                .filter(
                    SalePrice.year == year,
                    SalePrice.quarter == quarter,
                    SalePrice.property_type == "all",
                )
                .order_by(SalePrice.price_per_m2.desc())
                .all()
            )
            return [
                {
                    "district_code": d.code,
                    "district_name": d.name,
                    "price_per_m2": sp.price_per_m2,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "transactions": sp.transactions,
                    "period": f"{year} Q{quarter}",
                }
                for sp, d in rows
            ]

    # ── Rental analysis ────────────────────────────────────────────────────────

    def get_rental_analysis(
        self, year: int | None = None, quarter: int | None = None
    ) -> list[dict]:
        """Return rental price + yield per district."""
        with db_session() as db:
            if year is None or quarter is None:
                latest = self._latest_period(db, RentalPrice)
                if not latest:
                    return []
                year, quarter = latest

            rows = (
                db.query(RentalPrice, SalePrice, District)
                .join(District, RentalPrice.district_id == District.id)
                .join(
                    SalePrice,
                    (SalePrice.district_id == RentalPrice.district_id)
                    & (SalePrice.year == year)
                    & (SalePrice.quarter == quarter)
                    & (SalePrice.property_type == "all"),
                )
                .filter(RentalPrice.year == year, RentalPrice.quarter == quarter)
                .all()
            )
            result = []
            for rental, sale, district in rows:
                yield_pct = (
                    round(rental.price_per_m2_month * 12 / sale.price_per_m2 * 100, 2)
                    if sale.price_per_m2
                    else None
                )
                result.append(
                    {
                        "district_code": district.code,
                        "district_name": district.name,
                        "rental_price_m2_month": rental.price_per_m2_month,
                        "sale_price_m2": sale.price_per_m2,
                        "gross_yield_pct": yield_pct,
                        "listings_count": rental.listings_count,
                    }
                )
            result.sort(key=lambda x: x.get("rental_price_m2_month", 0), reverse=True)
            return result

    # ── Mortgage statistics ────────────────────────────────────────────────────

    def get_mortgage_trends(self, from_year: int = 2019) -> list[dict]:
        """Return monthly mortgage statistics from the given year."""
        with db_session() as db:
            rows = (
                db.query(MortgageData)
                .filter(MortgageData.year >= from_year)
                .order_by(MortgageData.year, MortgageData.month)
                .all()
            )
            return [
                {
                    "year": r.year,
                    "month": r.month,
                    "period": f"{r.year}-{r.month:02d}",
                    "num_mortgages": r.num_mortgages,
                    "avg_amount_eur": r.avg_amount_eur,
                    "avg_interest_rate": r.avg_interest_rate,
                    "fixed_rate_pct": r.fixed_rate_pct,
                    "avg_duration_years": r.avg_duration_years,
                }
                for r in rows
            ]

    # ── IPV trends ────────────────────────────────────────────────────────────

    def get_ipv_trends(
        self, property_type: str = "all", from_year: int = 2019
    ) -> list[dict]:
        """Return Housing Price Index trend."""
        with db_session() as db:
            rows = (
                db.query(HousingPriceIndex)
                .filter(
                    HousingPriceIndex.year >= from_year,
                    HousingPriceIndex.property_type == property_type,
                )
                .order_by(HousingPriceIndex.year, HousingPriceIndex.quarter)
                .all()
            )
            return [
                {
                    "year": r.year,
                    "quarter": r.quarter,
                    "period": f"{r.year} Q{r.quarter}",
                    "index_value": r.index_value,
                    "annual_variation_pct": r.annual_variation_pct,
                    "quarterly_variation_pct": r.quarterly_variation_pct,
                    "property_type": r.property_type,
                }
                for r in rows
            ]

    # ── Affordability ─────────────────────────────────────────────────────────

    def get_affordability_metrics(self) -> dict[str, Any]:
        """Compute affordability metrics for Madrid."""
        with db_session() as db:
            latest = self._latest_period(db, SalePrice)
            if not latest:
                return {}
            year, quarter = latest
            avg_price = self._city_avg_price(db, year, quarter)
            avg_rental = self._city_avg_rental(db, year, quarter)

        if not avg_price:
            return {}

        # Assume 80 m² typical apartment
        typical_size = 80
        total_price = avg_price * typical_size
        # Mortgage payment (25 yr, 80% LTV) — rough estimate at current rates
        mortgage_rate = 0.035  # 3.5% as a representative rate
        loan = total_price * self.MORTGAGE_LTV
        n = self.MORTGAGE_YEARS * 12
        monthly_rate = mortgage_rate / 12
        monthly_payment = loan * monthly_rate / (1 - (1 + monthly_rate) ** -n)

        monthly_income = self.MADRID_AVG_INCOME_EUR / 12
        payment_ratio = round(monthly_payment / monthly_income * 100, 1)

        rental_total = (avg_rental * typical_size) if avg_rental else None
        rental_ratio = round(rental_total / monthly_income * 100, 1) if rental_total else None

        return {
            "typical_apartment_size_m2": typical_size,
            "avg_total_price_eur": round(total_price, 0),
            "monthly_mortgage_payment_eur": round(monthly_payment, 0),
            "monthly_income_eur": round(monthly_income, 0),
            "mortgage_to_income_pct": payment_ratio,
            "rental_monthly_eur": round(rental_total, 0) if rental_total else None,
            "rent_to_income_pct": rental_ratio,
            "years_of_income_to_buy": round(
                total_price / self.MADRID_AVG_INCOME_EUR, 1
            ),
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _latest_period(db: Session, model) -> tuple[int, int] | None:
        row = (
            db.query(func.max(model.year), func.max(model.quarter))
            .filter(model.year == db.query(func.max(model.year)).scalar_subquery())
            .first()
        )
        if row and row[0]:
            return int(row[0]), int(row[1])
        return None

    @staticmethod
    def _city_avg_price(db: Session, year: int, quarter: int) -> float | None:
        row = db.query(func.avg(SalePrice.price_per_m2)).filter(
            SalePrice.year == year,
            SalePrice.quarter == quarter,
            SalePrice.property_type == "all",
        ).scalar()
        return float(row) if row is not None else None

    @staticmethod
    def _city_avg_rental(db: Session, year: int, quarter: int) -> float | None:
        row = db.query(func.avg(RentalPrice.price_per_m2_month)).filter(
            RentalPrice.year == year, RentalPrice.quarter == quarter
        ).scalar()
        return float(row) if row is not None else None

    @staticmethod
    def _latest_mortgage_count(db: Session, year: int) -> int | None:
        row = db.query(func.sum(MortgageData.num_mortgages)).filter(
            MortgageData.year == year
        ).scalar()
        return int(row) if row is not None else None

    @staticmethod
    def _latest_ipv(
        db: Session, year: int, quarter: int
    ) -> HousingPriceIndex | None:
        return db.query(HousingPriceIndex).filter_by(
            year=year, quarter=quarter, property_type="all"
        ).first()

    def _years_to_buy(self, avg_price: float | None) -> float | None:
        if not avg_price:
            return None
        typical_price = avg_price * 80  # 80 m²
        savings_rate = 0.20  # 20% of income saved annually
        annual_savings = self.MADRID_AVG_INCOME_EUR * savings_rate
        deposit_needed = typical_price * (1 - self.MORTGAGE_LTV)
        return round(deposit_needed / annual_savings, 1)

    def _affordability_index(self, avg_price: float | None) -> float | None:
        """
        100 = exactly affordable at average income.
        >100 = more affordable, <100 = less affordable.
        """
        if not avg_price:
            return None
        # Threshold: 30% of gross income on housing
        threshold_monthly = self.MADRID_AVG_INCOME_EUR / 12 * 0.30
        mortgage_rate = 0.035
        loan = avg_price * 80 * self.MORTGAGE_LTV
        n = self.MORTGAGE_YEARS * 12
        r = mortgage_rate / 12
        monthly_payment = loan * r / (1 - (1 + r) ** -n)
        index = round(threshold_monthly / monthly_payment * 100, 1)
        return index
