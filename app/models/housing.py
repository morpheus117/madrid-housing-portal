"""SQLAlchemy ORM models for the Madrid Housing Market Portal."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── District ───────────────────────────────────────────────────────────────────
class District(Base):
    """Madrid administrative district (21 districts)."""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_es: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    area_km2: Mapped[float] = mapped_column(Float, nullable=True)
    population: Mapped[int] = mapped_column(Integer, nullable=True)

    # Relationships
    sale_prices: Mapped[list["SalePrice"]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )
    rental_prices: Mapped[list["RentalPrice"]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )
    forecasts: Mapped[list["PriceForecast"]] = relationship(
        back_populates="district", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<District {self.code}: {self.name}>"


# ── Sale Prices ────────────────────────────────────────────────────────────────
class SalePrice(Base):
    """Average sale price per m² for a district in a given period."""

    __tablename__ = "sale_prices"
    __table_args__ = (
        UniqueConstraint("district_id", "year", "quarter", name="uq_sale_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–4
    price_per_m2: Mapped[float] = mapped_column(Float, nullable=False)
    property_type: Mapped[str] = mapped_column(
        String(20), default="all"  # all | new | second_hand
    )
    transactions: Mapped[int] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="demo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    district: Mapped["District"] = relationship(back_populates="sale_prices")

    @property
    def period_label(self) -> str:
        return f"{self.year} Q{self.quarter}"

    @property
    def period_date(self) -> datetime:
        month = (self.quarter - 1) * 3 + 1
        return datetime(self.year, month, 1)


# ── Rental Prices ──────────────────────────────────────────────────────────────
class RentalPrice(Base):
    """Average rental price per m²/month for a district in a given period."""

    __tablename__ = "rental_prices"
    __table_args__ = (
        UniqueConstraint(
            "district_id", "year", "quarter", name="uq_rental_period"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_m2_month: Mapped[float] = mapped_column(Float, nullable=False)
    listings_count: Mapped[int] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="demo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    district: Mapped["District"] = relationship(back_populates="rental_prices")


# ── Housing Price Index (INE IPV) ──────────────────────────────────────────────
class HousingPriceIndex(Base):
    """INE Housing Price Index (Índice de Precios de Vivienda) for Madrid."""

    __tablename__ = "housing_price_index"
    __table_args__ = (
        UniqueConstraint("year", "quarter", "property_type", name="uq_ipv_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    property_type: Mapped[str] = mapped_column(
        String(20), default="all"  # all | new | second_hand
    )
    index_value: Mapped[float] = mapped_column(Float, nullable=False)
    annual_variation_pct: Mapped[float] = mapped_column(Float, nullable=True)
    quarterly_variation_pct: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="INE")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ── Mortgage Data ──────────────────────────────────────────────────────────────
class MortgageData(Base):
    """Monthly mortgage statistics for Madrid from INE."""

    __tablename__ = "mortgage_data"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_mortgage_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    num_mortgages: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_amount_eur: Mapped[float] = mapped_column(Float, nullable=False)
    avg_interest_rate: Mapped[float] = mapped_column(Float, nullable=True)
    fixed_rate_pct: Mapped[float] = mapped_column(Float, nullable=True)
    avg_duration_years: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="INE")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ── Price Forecasts ────────────────────────────────────────────────────────────
class PriceForecast(Base):
    """Stored price forecast produced by the forecasting service."""

    __tablename__ = "price_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "district_id", "forecast_year", "forecast_quarter", "model_name",
            name="uq_forecast",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    forecast_year: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_price_m2: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float] = mapped_column(Float, nullable=True)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.95)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    district: Mapped["District"] = relationship(back_populates="forecasts")


# ── Data Fetch Log ─────────────────────────────────────────────────────────────
class DataFetchLog(Base):
    """Audit log for every data-fetch run."""

    __tablename__ = "data_fetch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False  # success | error | skipped
    )
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<DataFetchLog {self.source} {self.status}>"
