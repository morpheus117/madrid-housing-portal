"""
Price forecasting service.

Implements three models:
  1. Linear regression  — fast baseline, used when data is scarce
  2. SARIMA             — seasonal ARIMA via statsmodels
  3. Ensemble           — weighted average of the two models

All models produce a point estimate plus a 95 % confidence interval.
Forecasts are stored in the price_forecasts table after generation.
"""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sqlalchemy.orm import Session

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from statsmodels.tsa.statespace.sarimax import SARIMAX


from app.database import db_session
from app.models.housing import District, PriceForecast, SalePrice


class ForecastingService:
    """Generate and persist price forecasts for Madrid districts."""

    # SARIMA order — (p,d,q)(P,D,Q,m)
    SARIMA_ORDER = (1, 1, 1)
    SARIMA_SEASONAL = (1, 1, 0, 4)  # quarterly seasonality (m=4)
    MIN_POINTS_SARIMA = 12  # minimum data points to fit SARIMA
    CONFIDENCE = 0.95

    # ── Public API ─────────────────────────────────────────────────────────────

    def forecast_all_districts(self, periods: int = 8) -> dict[str, list[dict]]:
        """Generate forecasts for every district.  Returns mapping code→rows."""
        results: dict[str, list[dict]] = {}
        with db_session() as db:
            districts = db.query(District).all()
            for district in districts:
                rows = self._forecast_district(db, district, periods)
                results[district.code] = rows
        return results

    def forecast_district(
        self, district_code: str, periods: int = 8
    ) -> list[dict]:
        """Return forecast rows for a single district, saving to DB."""
        with db_session() as db:
            district = db.query(District).filter_by(code=district_code).first()
            if district is None:
                logger.warning(f"District {district_code} not found.")
                return []
            return self._forecast_district(db, district, periods)

    def get_stored_forecasts(
        self, district_code: str | None = None, model_name: str = "ensemble"
    ) -> list[dict]:
        """Retrieve stored forecasts from the database."""
        with db_session() as db:
            query = db.query(PriceForecast)
            if district_code:
                district = db.query(District).filter_by(code=district_code).first()
                if district:
                    query = query.filter_by(district_id=district.id)
            query = query.filter_by(model_name=model_name)
            rows = query.order_by(
                PriceForecast.forecast_year, PriceForecast.forecast_quarter
            ).all()
            return [self._forecast_to_dict(r) for r in rows]

    # ── Core forecast logic ────────────────────────────────────────────────────

    def _forecast_district(
        self, db: Session, district: District, periods: int
    ) -> list[dict]:
        ts = self._load_time_series(db, district.id)
        if len(ts) < 4:
            logger.warning(
                f"Not enough data to forecast district {district.code} "
                f"(found {len(ts)} points, need ≥4)."
            )
            return []

        # Run models
        linear_fc = self._linear_forecast(ts, periods)
        sarima_fc = (
            self._sarima_forecast(ts, periods)
            if len(ts) >= self.MIN_POINTS_SARIMA
            else linear_fc
        )
        ensemble_fc = self._ensemble_forecast(linear_fc, sarima_fc)

        # Persist all three
        all_rows: list[dict] = []
        for model_name, fc in [
            ("linear", linear_fc),
            ("sarima", sarima_fc),
            ("ensemble", ensemble_fc),
        ]:
            for row in fc:
                self._save_forecast(db, district.id, model_name, row)
                all_rows.append({**row, "model": model_name, "district_code": district.code})

        return [r for r in all_rows if r["model"] == "ensemble"]

    # ── Time-series helpers ────────────────────────────────────────────────────

    def _load_time_series(self, db: Session, district_id: int) -> pd.Series:
        """Return quarterly price series as a pandas Series indexed by period."""
        rows = (
            db.query(SalePrice)
            .filter_by(district_id=district_id, property_type="all")
            .order_by(SalePrice.year, SalePrice.quarter)
            .all()
        )
        if not rows:
            return pd.Series(dtype=float)
        index = pd.PeriodIndex(
            [pd.Period(year=r.year, quarter=r.quarter, freq="Q") for r in rows],
            freq="Q",
        )
        values = [r.price_per_m2 for r in rows]
        return pd.Series(values, index=index)

    @staticmethod
    def _next_periods(ts: pd.Series, n: int) -> list[pd.Period]:
        last = ts.index[-1]
        return [last + i for i in range(1, n + 1)]

    # ── Linear regression forecast ─────────────────────────────────────────────

    def _linear_forecast(self, ts: pd.Series, periods: int) -> list[dict]:
        X = np.arange(len(ts)).reshape(-1, 1)
        y = ts.values

        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)
        model = LinearRegression().fit(X_poly, y)

        n = len(ts)
        X_future = np.arange(n, n + periods).reshape(-1, 1)
        X_future_poly = poly.transform(X_future)
        preds = model.predict(X_future_poly)

        # Simple residual std for CI
        residuals = y - model.predict(X_poly)
        sigma = np.std(residuals)
        z = 1.96  # 95% CI

        future_periods = self._next_periods(ts, periods)
        return [
            {
                "year": p.year,
                "quarter": p.quarter,
                "predicted_price_m2": round(float(max(0, preds[i])), 2),
                "lower_bound": round(float(max(0, preds[i] - z * sigma)), 2),
                "upper_bound": round(float(preds[i] + z * sigma), 2),
                "confidence_level": self.CONFIDENCE,
            }
            for i, p in enumerate(future_periods)
        ]

    # ── SARIMA forecast ────────────────────────────────────────────────────────

    def _sarima_forecast(self, ts: pd.Series, periods: int) -> list[dict]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = SARIMAX(
                    ts.values,
                    order=self.SARIMA_ORDER,
                    seasonal_order=self.SARIMA_SEASONAL,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                fitted = model.fit(disp=False, maxiter=200)
                forecast_obj = fitted.get_forecast(steps=periods)
                means = forecast_obj.predicted_mean
                ci = forecast_obj.conf_int(alpha=1 - self.CONFIDENCE)

            future_periods = self._next_periods(ts, periods)
            return [
                {
                    "year": p.year,
                    "quarter": p.quarter,
                    "predicted_price_m2": round(float(max(0, means[i])), 2),
                    "lower_bound": round(float(max(0, ci[i, 0])), 2),
                    "upper_bound": round(float(ci[i, 1]), 2),
                    "confidence_level": self.CONFIDENCE,
                }
                for i, p in enumerate(future_periods)
            ]
        except Exception as exc:
            logger.warning(f"SARIMA failed: {exc} — falling back to linear.")
            return self._linear_forecast(ts, periods)

    # ── Ensemble ────────────────────────────────────────────────────────────────

    @staticmethod
    def _ensemble_forecast(
        linear: list[dict], sarima: list[dict], w_sarima: float = 0.65
    ) -> list[dict]:
        w_linear = 1 - w_sarima
        result = []
        for lin, sar in zip(linear, sarima):
            pred = w_linear * lin["predicted_price_m2"] + w_sarima * sar["predicted_price_m2"]
            lower = w_linear * lin["lower_bound"] + w_sarima * sar["lower_bound"]
            upper = w_linear * lin["upper_bound"] + w_sarima * sar["upper_bound"]
            result.append(
                {
                    "year": lin["year"],
                    "quarter": lin["quarter"],
                    "predicted_price_m2": round(pred, 2),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                    "confidence_level": lin["confidence_level"],
                }
            )
        return result

    # ── Persistence ────────────────────────────────────────────────────────────

    def _save_forecast(
        self, db: Session, district_id: int, model_name: str, row: dict
    ) -> None:
        existing = db.query(PriceForecast).filter_by(
            district_id=district_id,
            model_name=model_name,
            forecast_year=row["year"],
            forecast_quarter=row["quarter"],
        ).first()
        if existing:
            existing.predicted_price_m2 = row["predicted_price_m2"]
            existing.lower_bound = row["lower_bound"]
            existing.upper_bound = row["upper_bound"]
            existing.generated_at = datetime.utcnow()
        else:
            db.add(
                PriceForecast(
                    district_id=district_id,
                    model_name=model_name,
                    forecast_year=row["year"],
                    forecast_quarter=row["quarter"],
                    predicted_price_m2=row["predicted_price_m2"],
                    lower_bound=row["lower_bound"],
                    upper_bound=row["upper_bound"],
                    confidence_level=row["confidence_level"],
                )
            )

    @staticmethod
    def _forecast_to_dict(row: PriceForecast) -> dict:
        return {
            "year": row.forecast_year,
            "quarter": row.forecast_quarter,
            "predicted_price_m2": row.predicted_price_m2,
            "lower_bound": row.lower_bound,
            "upper_bound": row.upper_bound,
            "confidence_level": row.confidence_level,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }
