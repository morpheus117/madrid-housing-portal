"""
Dash callback definitions.

All data fetching uses the AnalyticsService and ForecastingService directly
(within the same process) rather than making HTTP calls to the FastAPI layer,
which avoids latency and simplifies deployment.
"""

from __future__ import annotations

from datetime import datetime

import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dash_table, html
from loguru import logger

from app.dashboard.charts import (
    _empty_chart,
    district_bar_chart,
    district_map_chart,
    forecast_chart,
    affordability_gauge,
    ipv_chart,
    mortgage_rate_chart,
    mortgage_volume_chart,
    price_trend_chart,
    price_yield_scatter,
    rental_yield_chart,
)
from app.services.analytics import AnalyticsService
from app.services.forecasting import ForecastingService

analytics = AnalyticsService()
forecasting = ForecastingService()

COLORS = {
    "bg": "#0d1117", "card": "#161b22", "border": "#30363d",
    "primary": "#4FC3F7", "secondary": "#EF5350", "accent": "#FFD54F",
    "green": "#66BB6A", "text": "#E6EDF3", "muted": "#8B949E",
}

TABLE_STYLE = dict(
    style_table={"overflowX": "auto"},
    style_header={
        "backgroundColor": "#21262d",
        "color": COLORS["text"],
        "fontWeight": "600",
        "border": f"1px solid {COLORS['border']}",
        "fontSize": "12px",
    },
    style_cell={
        "backgroundColor": COLORS["card"],
        "color": COLORS["text"],
        "border": f"1px solid {COLORS['border']}",
        "fontSize": "12px",
        "padding": "8px 12px",
        "textAlign": "left",
    },
    style_data_conditional=[
        {
            "if": {"row_index": "odd"},
            "backgroundColor": "#1c2128",
        }
    ],
    page_size=21,
    sort_action="native",
    filter_action="native",
)


def register_callbacks(app) -> None:
    """Register all Dash callbacks with the given Dash app instance."""

    # ── Populate district dropdown ─────────────────────────────────────────────

    @app.callback(
        Output("filter-district", "options"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_district_options(_n):
        try:
            snapshot = analytics.get_district_snapshot()
            options = [{"label": "All Districts", "value": "all"}] + [
                {"label": d["district_name"], "value": d["district_code"]}
                for d in snapshot
            ]
            return options
        except Exception as exc:
            logger.error(f"District dropdown error: {exc}")
            return [{"label": "All Districts", "value": "all"}]

    # ── Header: last updated ───────────────────────────────────────────────────

    @app.callback(
        Output("header-last-updated", "children"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_last_updated(_n):
        return datetime.now().strftime("%d %b %Y %H:%M")

    # ── KPI cards ──────────────────────────────────────────────────────────────

    @app.callback(
        Output("kpi-avg-price-value", "children"),
        Output("kpi-avg-price-delta", "children"),
        Output("kpi-yoy-change-value", "children"),
        Output("kpi-yoy-change-delta", "style"),
        Output("kpi-rental-price-value", "children"),
        Output("kpi-rental-price-delta", "children"),
        Output("kpi-yield-value", "children"),
        Output("kpi-yield-delta", "children"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_kpis(_n):
        try:
            s = analytics.get_market_summary()
            if not s:
                return ("—",) * 8

            price = f"€{s['avg_sale_price_m2']:,.0f}" if s.get("avg_sale_price_m2") else "—"
            yoy = s.get("yoy_price_change_pct")
            yoy_str = f"{yoy:+.1f}%" if yoy is not None else "—"
            yoy_color = COLORS["green"] if (yoy or 0) >= 0 else COLORS["secondary"]
            yoy_style = {"fontSize": "22px", "fontWeight": "700", "color": yoy_color}

            rental = f"€{s['avg_rental_m2_month']:.1f}" if s.get("avg_rental_m2_month") else "—"
            gross_yield = f"{s['gross_rental_yield_pct']:.2f}%" if s.get("gross_rental_yield_pct") else "—"
            period = s.get("period", "")

            return (
                price, period,
                yoy_str, yoy_style,
                rental, f"Gross yield: {gross_yield}",
                gross_yield, f"Period: {period}",
            )
        except Exception as exc:
            logger.error(f"KPI update error: {exc}")
            return ("—",) * 8

    # ── Overview tab ───────────────────────────────────────────────────────────

    @app.callback(
        Output("overview-trend", "figure"),
        Input("filter-from-year", "value"),
        Input("filter-property-type", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_overview_trend(from_year, prop_type, _n):
        try:
            data = analytics.get_price_trends(property_type=prop_type, from_year=from_year)
            return price_trend_chart(data, "Madrid City — Avg Sale Price Trend (€/m²)")
        except Exception as exc:
            logger.error(f"Overview trend error: {exc}")
            return _empty_chart("Data unavailable")

    @app.callback(
        Output("overview-ipv", "figure"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_overview_ipv(_n):
        try:
            data = analytics.get_ipv_trends(property_type="all", from_year=2019)
            return ipv_chart(data)
        except Exception as exc:
            logger.error(f"IPV overview error: {exc}")
            return _empty_chart("IPV data unavailable")

    @app.callback(
        Output("overview-district-bar", "figure"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_overview_district_bar(_n):
        try:
            data = analytics.get_district_snapshot()
            return district_bar_chart(data, "Current Price per m² by District")
        except Exception as exc:
            logger.error(f"District bar error: {exc}")
            return _empty_chart("Data unavailable")

    # ── Price Trends tab ───────────────────────────────────────────────────────

    @app.callback(
        Output("trends-price", "figure"),
        Input("filter-district", "value"),
        Input("filter-property-type", "value"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_trends_price(district, prop_type, from_year, _n):
        try:
            d = None if district == "all" else district
            data = analytics.get_price_trends(
                district_code=d, property_type=prop_type, from_year=from_year
            )
            label = "All Districts" if district == "all" else district
            return price_trend_chart(
                data, f"Sale Price Trend — {label} ({prop_type})"
            )
        except Exception as exc:
            logger.error(f"Trends price error: {exc}")
            return _empty_chart("Data unavailable")

    @app.callback(
        Output("trends-new-vs-used", "figure"),
        Input("filter-district", "value"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_new_vs_used(district, from_year, _n):
        try:
            d = None if district == "all" else district
            all_data = []
            for ptype in ("new", "second_hand"):
                rows = analytics.get_price_trends(
                    district_code=d, property_type=ptype, from_year=from_year
                )
                for r in rows:
                    r["district"] = ptype.replace("_", " ").title()
                all_data.extend(rows)
            return price_trend_chart(all_data, "New vs Second-Hand Prices")
        except Exception as exc:
            logger.error(f"New vs used error: {exc}")
            return _empty_chart("Data unavailable")

    @app.callback(
        Output("trends-ipv-detail", "figure"),
        Input("filter-property-type", "value"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_ipv_detail(prop_type, from_year, _n):
        try:
            data = analytics.get_ipv_trends(
                property_type=prop_type, from_year=from_year
            )
            return ipv_chart(data)
        except Exception as exc:
            logger.error(f"IPV detail error: {exc}")
            return _empty_chart("IPV data unavailable")

    # ── Districts tab ──────────────────────────────────────────────────────────

    @app.callback(
        Output("district-map", "figure"),
        Output("district-bar", "figure"),
        Output("district-table", "children"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_district_views(_n):
        try:
            data = analytics.get_district_snapshot()
            map_fig = district_map_chart(data)
            bar_fig = district_bar_chart(data, "Price per m² by District")

            # Build table
            table_data = [
                {
                    "Rank": i + 1,
                    "District": d["district_name"],
                    "Price (€/m²)": f"{d['price_per_m2']:,.0f}",
                    "Transactions": d.get("transactions", "—"),
                    "Period": d.get("period", "—"),
                }
                for i, d in enumerate(
                    sorted(data, key=lambda x: x["price_per_m2"], reverse=True)
                )
            ]
            table = dash_table.DataTable(
                data=table_data,
                columns=[{"name": c, "id": c} for c in table_data[0].keys()],
                **TABLE_STYLE,
            )
            return map_fig, bar_fig, table
        except Exception as exc:
            logger.error(f"District view error: {exc}")
            empty = _empty_chart("Data unavailable")
            return empty, empty, html.P("Data unavailable", style={"color": COLORS["muted"]})

    # ── Rental tab ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("rental-yield-bar", "figure"),
        Output("rental-scatter", "figure"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_rental_charts(_n):
        try:
            data = analytics.get_rental_analysis()
            return rental_yield_chart(data), price_yield_scatter(data)
        except Exception as exc:
            logger.error(f"Rental charts error: {exc}")
            empty = _empty_chart("Data unavailable")
            return empty, empty

    @app.callback(
        Output("rental-trend", "figure"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_rental_trend(from_year, _n):
        try:
            # Show rental price trend for all districts combined
            data = analytics.get_price_trends(property_type="all", from_year=from_year)
            # Approximate rental from sale using RENTAL_SALE_RATIO
            for r in data:
                r["price_per_m2"] = round(r["price_per_m2"] * 0.003, 2)
                r["district"] = "Estimated Rental (€/m²/mo)"
            return price_trend_chart(data, "Estimated Rental Price Trend (€/m²/month)")
        except Exception as exc:
            logger.error(f"Rental trend error: {exc}")
            return _empty_chart("Data unavailable")

    # ── Forecast tab ───────────────────────────────────────────────────────────

    @app.callback(
        Output("forecast-main", "figure"),
        Output("forecast-table", "children"),
        Output("forecast-affordability-gauge", "figure"),
        Output("forecast-affordability-metrics", "children"),
        Input("filter-district", "value"),
        Input("filter-forecast-periods", "value"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_forecast(district, periods, from_year, _n):
        try:
            d = None if district == "all" else district
            # Historical data
            historical = analytics.get_price_trends(
                district_code=d, property_type="all", from_year=from_year
            )

            # Forecast
            if d:
                fc_rows = forecasting.get_stored_forecasts(
                    district_code=d, model_name="ensemble"
                )
                if not fc_rows:
                    fc_rows = forecasting.forecast_district(d, periods=periods or 8)
            else:
                # City-wide: use district "01" (Centro) as representative
                fc_rows = forecasting.get_stored_forecasts(
                    district_code="01", model_name="ensemble"
                )
                if not fc_rows:
                    fc_rows = forecasting.forecast_district("01", periods=periods or 8)

            label = "All Districts" if not d else d
            fig = forecast_chart(
                historical, fc_rows,
                title=f"Price Forecast — {label}",
            )

            # Affordability gauge
            aff = analytics.get_affordability_metrics()
            gauge = affordability_gauge(aff.get("affordability_index"))

            # Affordability metrics panel
            metrics_panel = _affordability_panel(aff)

            # Forecast table
            if fc_rows:
                table_data = [
                    {
                        "Period": f"{r['year']} Q{r['quarter']}",
                        "Forecast (€/m²)": f"{r['predicted_price_m2']:,.0f}",
                        "Lower Bound": f"{r['lower_bound']:,.0f}" if r.get("lower_bound") else "—",
                        "Upper Bound": f"{r['upper_bound']:,.0f}" if r.get("upper_bound") else "—",
                        "Confidence": f"{r.get('confidence_level', 0.95):.0%}",
                    }
                    for r in fc_rows
                ]
                table = dash_table.DataTable(
                    data=table_data,
                    columns=[{"name": c, "id": c} for c in table_data[0].keys()],
                    **TABLE_STYLE,
                )
            else:
                table = html.P(
                    "No forecast available. Ensure data is seeded.",
                    style={"color": COLORS["muted"]},
                )

            return fig, table, gauge, metrics_panel

        except Exception as exc:
            logger.error(f"Forecast tab error: {exc}")
            empty = _empty_chart("Forecast unavailable")
            empty_gauge = affordability_gauge(None)
            return (
                empty,
                html.P("Error generating forecast.", style={"color": COLORS["secondary"]}),
                empty_gauge,
                html.P("Error", style={"color": COLORS["secondary"]}),
            )

    # ── Mortgage tab ───────────────────────────────────────────────────────────

    @app.callback(
        Output("mortgage-volume", "figure"),
        Output("mortgage-rates", "figure"),
        Output("mortgage-stats-panel", "children"),
        Input("filter-from-year", "value"),
        Input("interval-refresh", "n_intervals"),
    )
    def update_mortgage_charts(from_year, _n):
        try:
            data = analytics.get_mortgage_trends(from_year=from_year)
            vol_fig = mortgage_volume_chart(data)
            rate_fig = mortgage_rate_chart(data)

            # Stats panel
            if data:
                latest = data[-1]
                stats = [
                    _stat_row("Latest Month", latest.get("period", "—")),
                    _stat_row("Mortgages", f"{latest.get('num_mortgages', 0):,}"),
                    _stat_row(
                        "Avg Amount",
                        f"€{latest.get('avg_amount_eur', 0):,.0f}",
                    ),
                    _stat_row(
                        "Avg Rate",
                        f"{latest.get('avg_interest_rate', 0):.2f}%",
                    ),
                    _stat_row(
                        "Fixed Rate Share",
                        f"{latest.get('fixed_rate_pct', 0):.1f}%",
                    ),
                    _stat_row(
                        "Avg Duration",
                        f"{latest.get('avg_duration_years', 0):.1f} yrs",
                    ),
                ]
                panel = html.Div(stats)
            else:
                panel = html.P("No data", style={"color": COLORS["muted"]})

            return vol_fig, rate_fig, panel
        except Exception as exc:
            logger.error(f"Mortgage tab error: {exc}")
            empty = _empty_chart("Data unavailable")
            return (
                empty,
                empty,
                html.P("Error loading data.", style={"color": COLORS["secondary"]}),
            )


# ── Utility helpers ────────────────────────────────────────────────────────────

def _stat_row(label: str, value: str) -> html.Div:
    return html.Div(
        [
            html.Span(label, style={"color": COLORS["muted"], "fontSize": "12px"}),
            html.Span(
                value,
                style={
                    "color": COLORS["text"],
                    "fontSize": "14px",
                    "fontWeight": "600",
                    "float": "right",
                },
            ),
        ],
        style={
            "padding": "8px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
            "overflow": "hidden",
        },
    )


def _affordability_panel(aff: dict) -> html.Div:
    if not aff:
        return html.P("No affordability data.", style={"color": COLORS["muted"]})
    rows = [
        _stat_row("80 m² Apt Price", f"€{aff.get('avg_total_price_eur', 0):,.0f}"),
        _stat_row("Monthly Mortgage", f"€{aff.get('monthly_mortgage_payment_eur', 0):,.0f}"),
        _stat_row("Avg Monthly Income", f"€{aff.get('monthly_income_eur', 0):,.0f}"),
        _stat_row(
            "Mortgage / Income",
            f"{aff.get('mortgage_to_income_pct', 0):.1f}%",
        ),
        _stat_row("Yrs Income to Buy", f"{aff.get('years_of_income_to_buy', 0):.1f}"),
    ]
    return html.Div(rows)
