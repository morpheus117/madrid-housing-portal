"""
Plotly Dash layout for the Madrid Housing Market Portal.

Generates the full page structure: header, filter sidebar, KPI row,
and tabbed content area.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

# ── Brand colours (mirrors charts.py palette) ──────────────────────────────────
COLORS = {
    "bg": "#0d1117",
    "card": "#161b22",
    "border": "#30363d",
    "primary": "#4FC3F7",
    "secondary": "#EF5350",
    "accent": "#FFD54F",
    "text": "#E6EDF3",
    "muted": "#8B949E",
}

# ── Custom inline styles ───────────────────────────────────────────────────────
CARD_STYLE = {
    "background": COLORS["card"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "8px",
    "padding": "16px",
}
KPI_CARD_STYLE = {
    **CARD_STYLE,
    "textAlign": "center",
    "minHeight": "120px",
    "display": "flex",
    "flexDirection": "column",
    "justifyContent": "center",
}
HEADER_STYLE = {
    "background": "linear-gradient(90deg, #0d1117 0%, #1a1f2e 100%)",
    "borderBottom": f"2px solid {COLORS['secondary']}",
    "padding": "16px 24px",
}


# ── KPI Card ──────────────────────────────────────────────────────────────────

def kpi_card(card_id: str, title: str, icon: str = "📊") -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Div(icon, style={"fontSize": "28px", "marginBottom": "4px"}),
                html.Div(
                    id=f"kpi-{card_id}-value",
                    children="—",
                    style={
                        "fontSize": "22px",
                        "fontWeight": "700",
                        "color": COLORS["primary"],
                        "lineHeight": "1.2",
                    },
                ),
                html.Div(
                    id=f"kpi-{card_id}-delta",
                    children="",
                    style={"fontSize": "12px", "color": COLORS["muted"]},
                ),
                html.Div(
                    title,
                    style={
                        "fontSize": "11px",
                        "color": COLORS["muted"],
                        "marginTop": "4px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.05em",
                    },
                ),
            ],
            style=KPI_CARD_STYLE,
        ),
        xs=12, sm=6, md=3,
    )


# ── Header ────────────────────────────────────────────────────────────────────

def create_header() -> html.Div:
    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Span(
                                "🏠",
                                style={"fontSize": "28px", "marginRight": "12px"},
                            ),
                            html.Span(
                                "Madrid Housing Market Portal",
                                style={
                                    "fontSize": "22px",
                                    "fontWeight": "700",
                                    "color": COLORS["text"],
                                    "verticalAlign": "middle",
                                },
                            ),
                            html.Span(
                                " | Real Estate Analytics",
                                style={
                                    "fontSize": "14px",
                                    "color": COLORS["muted"],
                                    "marginLeft": "8px",
                                    "verticalAlign": "middle",
                                },
                            ),
                        ]
                    ),
                    md=8,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Span(
                                "Last updated: ",
                                style={"color": COLORS["muted"], "fontSize": "12px"},
                            ),
                            html.Span(
                                id="header-last-updated",
                                children="—",
                                style={"color": COLORS["accent"], "fontSize": "12px"},
                            ),
                            html.Span(
                                " · ",
                                style={"color": COLORS["muted"], "margin": "0 8px"},
                            ),
                            dbc.Badge(
                                "LIVE",
                                color="success",
                                className="ms-1",
                                style={"fontSize": "10px"},
                            ),
                        ],
                        style={"textAlign": "right"},
                    ),
                    md=4,
                ),
            ],
            align="center",
        ),
        style=HEADER_STYLE,
    )


# ── Filter bar ────────────────────────────────────────────────────────────────

def create_filters() -> html.Div:
    dropdown_style = {
        "backgroundColor": COLORS["card"],
        "color": COLORS["text"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
    }

    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label(
                            "District",
                            style={"fontSize": "11px", "color": COLORS["muted"],
                                   "textTransform": "uppercase"},
                        ),
                        dcc.Dropdown(
                            id="filter-district",
                            options=[{"label": "All Districts", "value": "all"}],
                            value="all",
                            clearable=False,
                            style=dropdown_style,
                            className="dark-dropdown",
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        html.Label(
                            "Property Type",
                            style={"fontSize": "11px", "color": COLORS["muted"],
                                   "textTransform": "uppercase"},
                        ),
                        dcc.Dropdown(
                            id="filter-property-type",
                            options=[
                                {"label": "All Types", "value": "all"},
                                {"label": "New Construction", "value": "new"},
                                {"label": "Second-Hand", "value": "second_hand"},
                            ],
                            value="all",
                            clearable=False,
                            style=dropdown_style,
                            className="dark-dropdown",
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        html.Label(
                            "From Year",
                            style={"fontSize": "11px", "color": COLORS["muted"],
                                   "textTransform": "uppercase"},
                        ),
                        dcc.Dropdown(
                            id="filter-from-year",
                            options=[
                                {"label": str(y), "value": y}
                                for y in range(2019, 2026)
                            ],
                            value=2019,
                            clearable=False,
                            style=dropdown_style,
                            className="dark-dropdown",
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        html.Label(
                            "Forecast Periods (Quarters)",
                            style={"fontSize": "11px", "color": COLORS["muted"],
                                   "textTransform": "uppercase"},
                        ),
                        dcc.Slider(
                            id="filter-forecast-periods",
                            min=2,
                            max=16,
                            step=2,
                            value=8,
                            marks={i: str(i) for i in range(2, 17, 2)},
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ],
                    md=4,
                ),
            ],
            className="g-3",
            align="center",
        ),
        style={
            **CARD_STYLE,
            "marginBottom": "16px",
            "borderLeft": f"3px solid {COLORS['secondary']}",
        },
    )


# ── KPI Row ───────────────────────────────────────────────────────────────────

def create_kpi_row() -> dbc.Row:
    return dbc.Row(
        [
            kpi_card("avg-price", "Avg Sale Price / m²", "🏷️"),
            kpi_card("yoy-change", "Year-over-Year Change", "📈"),
            kpi_card("rental-price", "Avg Rental / m² / mo", "🔑"),
            kpi_card("yield", "Gross Rental Yield", "💰"),
        ],
        className="g-2 mb-3",
    )


# ── Tab content panels ────────────────────────────────────────────────────────

def _graph(graph_id: str, height: int = 420) -> dcc.Graph:
    return dcc.Graph(
        id=graph_id,
        config={"displayModeBar": True, "displaylogo": False},
        style={"height": f"{height}px"},
    )


def overview_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("overview-trend"), style=CARD_STYLE),
                        md=8,
                    ),
                    dbc.Col(
                        html.Div(_graph("overview-ipv", height=420), style=CARD_STYLE),
                        md=4,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("overview-district-bar", height=500), style=CARD_STYLE),
                        md=12,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


def trends_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("trends-price"), style=CARD_STYLE),
                        md=12,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("trends-new-vs-used", height=400), style=CARD_STYLE),
                        md=6,
                    ),
                    dbc.Col(
                        html.Div(_graph("trends-ipv-detail", height=400), style=CARD_STYLE),
                        md=6,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


def districts_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("district-map", height=480), style=CARD_STYLE),
                        md=7,
                    ),
                    dbc.Col(
                        html.Div(_graph("district-bar", height=480), style=CARD_STYLE),
                        md=5,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H6(
                                    "District Price Ranking",
                                    style={"color": COLORS["text"], "marginBottom": "12px"},
                                ),
                                html.Div(id="district-table"),
                            ],
                            style=CARD_STYLE,
                        ),
                        md=12,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


def rental_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("rental-yield-bar", height=500), style=CARD_STYLE),
                        md=6,
                    ),
                    dbc.Col(
                        html.Div(_graph("rental-scatter", height=500), style=CARD_STYLE),
                        md=6,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("rental-trend"), style=CARD_STYLE),
                        md=12,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


def forecast_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Alert(
                            [
                                html.Strong("Model: "),
                                "Ensemble (65% SARIMA + 35% Polynomial Regression). "
                                "Shaded area = 95% confidence interval.",
                            ],
                            color="info",
                            style={"fontSize": "13px", "padding": "10px 16px"},
                        ),
                        md=12,
                    ),
                ],
                className="mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("forecast-main", height=480), style=CARD_STYLE),
                        md=8,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                _graph("forecast-affordability-gauge", height=260),
                                html.Hr(style={"borderColor": COLORS["border"]}),
                                html.Div(id="forecast-affordability-metrics"),
                            ],
                            style=CARD_STYLE,
                        ),
                        md=4,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H6(
                                    "Forecast Table",
                                    style={"color": COLORS["text"], "marginBottom": "12px"},
                                ),
                                html.Div(id="forecast-table"),
                            ],
                            style=CARD_STYLE,
                        ),
                        md=12,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


def mortgage_tab() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("mortgage-volume"), style=CARD_STYLE),
                        md=12,
                    ),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(_graph("mortgage-rates"), style=CARD_STYLE),
                        md=8,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H6(
                                    "Mortgage Market Stats",
                                    style={"color": COLORS["text"], "marginBottom": "12px"},
                                ),
                                html.Div(id="mortgage-stats-panel"),
                            ],
                            style=CARD_STYLE,
                        ),
                        md=4,
                    ),
                ],
                className="g-3",
            ),
        ]
    )


# ── Main layout ────────────────────────────────────────────────────────────────

def create_layout() -> html.Div:
    """Return the root Dash layout element."""
    return html.Div(
        [
            # Periodic data refresh trigger
            dcc.Interval(
                id="interval-refresh",
                interval=5 * 60 * 1000,  # 5 minutes
                n_intervals=0,
            ),

            # Header
            create_header(),

            # Main content
            html.Div(
                [
                    # Filters
                    create_filters(),

                    # KPI row
                    create_kpi_row(),

                    # Tabs
                    dbc.Tabs(
                        [
                            dbc.Tab(overview_tab(), label="Overview", tab_id="tab-overview"),
                            dbc.Tab(trends_tab(), label="Price Trends", tab_id="tab-trends"),
                            dbc.Tab(districts_tab(), label="Districts", tab_id="tab-districts"),
                            dbc.Tab(rental_tab(), label="Rental Market", tab_id="tab-rental"),
                            dbc.Tab(forecast_tab(), label="Forecasting", tab_id="tab-forecast"),
                            dbc.Tab(mortgage_tab(), label="Mortgage Market", tab_id="tab-mortgage"),
                        ],
                        id="main-tabs",
                        active_tab="tab-overview",
                        className="custom-tabs",
                    ),
                ],
                style={
                    "maxWidth": "1600px",
                    "margin": "0 auto",
                    "padding": "20px 24px",
                },
            ),
        ],
        style={
            "fontFamily": "Inter, 'Segoe UI', sans-serif",
            "backgroundColor": COLORS["bg"],
            "minHeight": "100vh",
            "color": COLORS["text"],
        },
    )
