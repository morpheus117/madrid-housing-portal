"""Pydantic response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DistrictSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    name_es: str
    latitude: float | None
    longitude: float | None
    area_km2: float | None
    population: int | None


class SalePriceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    quarter: int
    period: str
    price_per_m2: float
    transactions: int | None
    property_type: str


class RentalPriceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    quarter: int
    price_per_m2_month: float
    listings_count: int | None


class HousingPriceIndexSchema(BaseModel):
    year: int
    quarter: int
    period: str
    index_value: float
    annual_variation_pct: float | None
    quarterly_variation_pct: float | None
    property_type: str


class MortgageDataSchema(BaseModel):
    year: int
    month: int
    period: str
    num_mortgages: int
    avg_amount_eur: float
    avg_interest_rate: float | None
    fixed_rate_pct: float | None
    avg_duration_years: float | None


class PriceForecastSchema(BaseModel):
    year: int
    quarter: int
    predicted_price_m2: float
    lower_bound: float | None
    upper_bound: float | None
    confidence_level: float
    generated_at: str | None


class MarketSummarySchema(BaseModel):
    period: str
    avg_sale_price_m2: float | None
    yoy_price_change_pct: float | None
    avg_rental_m2_month: float | None
    gross_rental_yield_pct: float | None
    annual_mortgages: int | None
    ipv_annual_variation_pct: float | None
    years_to_buy: float | None
    affordability_index: float | None


class DistrictSnapshotSchema(BaseModel):
    district_code: str
    district_name: str
    price_per_m2: float
    latitude: float | None
    longitude: float | None
    transactions: int | None
    period: str


class RentalAnalysisSchema(BaseModel):
    district_code: str
    district_name: str
    rental_price_m2_month: float
    sale_price_m2: float
    gross_yield_pct: float | None
    listings_count: int | None


class AffordabilitySchema(BaseModel):
    typical_apartment_size_m2: int
    avg_total_price_eur: float
    monthly_mortgage_payment_eur: float
    monthly_income_eur: float
    mortgage_to_income_pct: float
    rental_monthly_eur: float | None
    rent_to_income_pct: float | None
    years_of_income_to_buy: float


class DataRefreshResponse(BaseModel):
    status: str
    message: str
    details: dict[str, Any] = {}
