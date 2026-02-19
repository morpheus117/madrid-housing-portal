"""
Reusable Plotly chart factory functions for the Madrid Housing Portal.

All charts use the portal's dark Madrid colour theme and return
plotly.graph_objects.Figure instances ready to embed in Dash components.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ── Brand palette ──────────────────────────────────────────────────────────────
PALETTE = {
    "bg": "#0d1117",
    "card": "#161b22",
    "border": "#30363d",
    "primary": "#4FC3F7",    # sky blue
    "secondary": "#EF5350",  # madrid red
    "accent": "#FFD54F",     # gold
    "green": "#66BB6A",
    "purple": "#AB47BC",
    "text": "#E6EDF3",
    "muted": "#8B949E",
    "grid": "#21262d",
}

LAYOUT_DEFAULTS = dict(
    paper_bgcolor=PALETTE["card"],
    plot_bgcolor=PALETTE["card"],
    font=dict(family="Inter, Segoe UI, sans-serif", color=PALETTE["text"], size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(bgcolor=PALETTE["card"], bordercolor=PALETTE["border"]),
    xaxis=dict(
        gridcolor=PALETTE["grid"], linecolor=PALETTE["border"],
        tickcolor=PALETTE["muted"], title_font=dict(color=PALETTE["muted"]),
    ),
    yaxis=dict(
        gridcolor=PALETTE["grid"], linecolor=PALETTE["border"],
        tickcolor=PALETTE["muted"], title_font=dict(color=PALETTE["muted"]),
    ),
)


def _apply_defaults(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(title=dict(text=title, font=dict(size=14, color=PALETTE["text"])), **LAYOUT_DEFAULTS)
    return fig


# ── Price trend line chart ─────────────────────────────────────────────────────

def price_trend_chart(data: list[dict], title: str = "Sale Price Trend (€/m²)") -> go.Figure:
    """
    Multi-series line chart of price per m² over time.
    *data* is a list of dicts with keys: period, price_per_m2, district.
    """
    if not data:
        return _empty_chart("No price trend data available")

    df = pd.DataFrame(data)
    fig = go.Figure()

    colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["accent"],
              PALETTE["green"], PALETTE["purple"]]

    for i, (district, grp) in enumerate(df.groupby("district")):
        grp = grp.sort_values("period")
        color = colors[i % len(colors)]
        fig.add_trace(
            go.Scatter(
                x=grp["period"],
                y=grp["price_per_m2"],
                mode="lines+markers",
                name=str(district),
                line=dict(color=color, width=2),
                marker=dict(size=5),
                hovertemplate=(
                    "<b>%{x}</b><br>%{y:,.0f} €/m²<extra>%{fullData.name}</extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Period",
        yaxis_title="€ / m²",
    )
    return _apply_defaults(fig, title)


# ── District bar chart ────────────────────────────────────────────────────────

def district_bar_chart(
    data: list[dict],
    title: str = "Price per m² by District",
    value_key: str = "price_per_m2",
    label: str = "€/m²",
) -> go.Figure:
    """Horizontal bar chart comparing districts."""
    if not data:
        return _empty_chart("No district data available")

    df = pd.DataFrame(data).sort_values(value_key, ascending=True)
    city_avg = df[value_key].mean()

    colors = [
        PALETTE["secondary"] if v >= city_avg else PALETTE["primary"]
        for v in df[value_key]
    ]

    fig = go.Figure(
        go.Bar(
            x=df[value_key],
            y=df["district_name"],
            orientation="h",
            marker=dict(color=colors),
            hovertemplate=f"<b>%{{y}}</b><br>%{{x:,.0f}} {label}<extra></extra>",
            text=df[value_key].apply(lambda v: f"{v:,.0f}"),
            textposition="outside",
            textfont=dict(color=PALETTE["text"], size=10),
        )
    )

    # City average line
    fig.add_vline(
        x=city_avg,
        line_dash="dash",
        line_color=PALETTE["accent"],
        annotation_text=f"City avg: {city_avg:,.0f}",
        annotation_font=dict(color=PALETTE["accent"]),
    )

    fig.update_layout(
        xaxis_title=label,
        yaxis_title="",
        showlegend=False,
        height=max(350, len(df) * 28),
    )
    return _apply_defaults(fig, title)


# ── Map chart ─────────────────────────────────────────────────────────────────

def district_map_chart(
    data: list[dict],
    title: str = "Madrid Housing Prices by District",
) -> go.Figure:
    """
    Bubble map of Madrid districts coloured by price per m².
    Uses scatter_mapbox with point markers (fallback when GeoJSON is unavailable).
    """
    if not data:
        return _empty_chart("No geographic data available")

    df = pd.DataFrame(data).dropna(subset=["latitude", "longitude"])
    if df.empty:
        return _empty_chart("No geographic coordinates available")

    min_p = df["price_per_m2"].min()
    max_p = df["price_per_m2"].max()

    fig = go.Figure(
        go.Scattermapbox(
            lat=df["latitude"],
            lon=df["longitude"],
            mode="markers+text",
            marker=dict(
                size=df["price_per_m2"].apply(lambda v: 12 + 18 * (v - min_p) / max(max_p - min_p, 1)),
                color=df["price_per_m2"],
                colorscale="RdYlBu_r",
                cmin=min_p,
                cmax=max_p,
                colorbar=dict(
                    title="€/m²",
                    thickness=12,
                    tickfont=dict(color=PALETTE["text"]),
                    title_font=dict(color=PALETTE["text"]),
                ),
                showscale=True,
            ),
            text=df["district_name"],
            textfont=dict(color="white", size=9),
            textposition="top center",
            customdata=df[["district_name", "price_per_m2"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Price: %{customdata[1]:,.0f} €/m²<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=40.416, lon=-3.703),
            zoom=10,
        ),
        paper_bgcolor=PALETTE["card"],
        font=dict(color=PALETTE["text"]),
        margin=dict(l=0, r=0, t=40, b=0),
        height=480,
        title=dict(text=title, font=dict(size=14, color=PALETTE["text"])),
    )
    return fig


# ── Forecast chart ────────────────────────────────────────────────────────────

def forecast_chart(
    historical: list[dict],
    forecast: list[dict],
    title: str = "Price Forecast",
) -> go.Figure:
    """Line chart with historical data + forecast and confidence interval."""
    fig = go.Figure()

    if historical:
        hist_df = pd.DataFrame(historical).sort_values("period")
        fig.add_trace(
            go.Scatter(
                x=hist_df["period"],
                y=hist_df["price_per_m2"],
                mode="lines+markers",
                name="Historical",
                line=dict(color=PALETTE["primary"], width=2),
                marker=dict(size=4),
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} €/m²<extra>Historical</extra>",
            )
        )

    if forecast:
        fc_df = pd.DataFrame(forecast)
        fc_df["period"] = fc_df.apply(
            lambda r: f"{int(r['year'])} Q{int(r['quarter'])}", axis=1
        )
        fc_df = fc_df.sort_values("period")

        # Confidence interval band
        fig.add_trace(
            go.Scatter(
                x=pd.concat([fc_df["period"], fc_df["period"].iloc[::-1]]),
                y=pd.concat([fc_df["upper_bound"], fc_df["lower_bound"].iloc[::-1]]),
                fill="toself",
                fillcolor=f"rgba(239, 83, 80, 0.15)",
                line=dict(color="rgba(255,255,255,0)"),
                name="95% Confidence Interval",
                hoverinfo="skip",
            )
        )

        # Forecast line
        fig.add_trace(
            go.Scatter(
                x=fc_df["period"],
                y=fc_df["predicted_price_m2"],
                mode="lines+markers",
                name="Forecast",
                line=dict(color=PALETTE["secondary"], width=2, dash="dash"),
                marker=dict(size=6, symbol="diamond"),
                hovertemplate=(
                    "<b>%{x}</b><br>Forecast: %{y:,.0f} €/m²<extra>Forecast</extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Period",
        yaxis_title="€ / m²",
    )
    return _apply_defaults(fig, title)


# ── Rental yield chart ────────────────────────────────────────────────────────

def rental_yield_chart(data: list[dict]) -> go.Figure:
    """Bar chart of gross rental yield by district."""
    if not data:
        return _empty_chart("No rental data available")

    df = pd.DataFrame(data).sort_values("gross_yield_pct", ascending=True)
    avg_yield = df["gross_yield_pct"].mean()

    colors = [
        PALETTE["green"] if v >= 4.0 else PALETTE["accent"] if v >= 3.0 else PALETTE["secondary"]
        for v in df["gross_yield_pct"]
    ]

    fig = go.Figure(
        go.Bar(
            x=df["gross_yield_pct"],
            y=df["district_name"],
            orientation="h",
            marker=dict(color=colors),
            hovertemplate="<b>%{y}</b><br>Yield: %{x:.2f}%<extra></extra>",
            text=df["gross_yield_pct"].apply(lambda v: f"{v:.2f}%"),
            textposition="outside",
            textfont=dict(color=PALETTE["text"], size=10),
        )
    )
    fig.add_vline(
        x=avg_yield,
        line_dash="dash",
        line_color=PALETTE["accent"],
        annotation_text=f"Avg: {avg_yield:.2f}%",
        annotation_font=dict(color=PALETTE["accent"]),
    )
    fig.update_layout(
        xaxis_title="Gross Rental Yield (%)",
        yaxis_title="",
        showlegend=False,
        height=max(350, len(df) * 28),
    )
    return _apply_defaults(fig, "Gross Rental Yield by District")


# ── Mortgage volume chart ─────────────────────────────────────────────────────

def mortgage_volume_chart(data: list[dict]) -> go.Figure:
    """Area chart of monthly mortgage count over time."""
    if not data:
        return _empty_chart("No mortgage data available")

    df = pd.DataFrame(data).sort_values("period")
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["num_mortgages"],
            mode="lines",
            name="Mortgages",
            fill="tozeroy",
            fillcolor=f"rgba(79, 195, 247, 0.2)",
            line=dict(color=PALETTE["primary"], width=2),
            hovertemplate="<b>%{x}</b><br>%{y:,} mortgages<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Number of Mortgages",
        hovermode="x unified",
    )
    return _apply_defaults(fig, "Monthly Mortgage Volume — Madrid")


def mortgage_rate_chart(data: list[dict]) -> go.Figure:
    """Dual-axis chart: interest rate + fixed-rate share over time."""
    if not data:
        return _empty_chart("No mortgage rate data available")

    df = pd.DataFrame(data).sort_values("period").dropna(
        subset=["avg_interest_rate", "fixed_rate_pct"]
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["avg_interest_rate"],
            name="Avg Interest Rate (%)",
            line=dict(color=PALETTE["secondary"], width=2),
            hovertemplate="<b>%{x}</b><br>Rate: %{y:.2f}%<extra>Avg Rate</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["fixed_rate_pct"],
            name="Fixed Rate Share (%)",
            line=dict(color=PALETTE["accent"], width=2, dash="dot"),
            yaxis="y2",
            hovertemplate="<b>%{x}</b><br>Fixed: %{y:.1f}%<extra>Fixed Share</extra>",
        )
    )

    fig.update_layout(
        yaxis=dict(title="Interest Rate (%)", side="left"),
        yaxis2=dict(
            title="Fixed Rate Share (%)",
            side="right",
            overlaying="y",
            range=[0, 100],
            showgrid=False,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _apply_defaults(fig, "Mortgage Rates & Fixed-Rate Share")


# ── IPV chart ─────────────────────────────────────────────────────────────────

def ipv_chart(data: list[dict]) -> go.Figure:
    """Dual-axis chart: IPV index + annual variation."""
    if not data:
        return _empty_chart("No IPV data available")

    df = pd.DataFrame(data).sort_values("period")
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["period"],
            y=df["index_value"],
            name="IPV Index",
            line=dict(color=PALETTE["primary"], width=2),
            hovertemplate="<b>%{x}</b><br>Index: %{y:.1f}<extra>IPV</extra>",
        )
    )

    var_df = df.dropna(subset=["annual_variation_pct"])
    if not var_df.empty:
        fig.add_trace(
            go.Bar(
                x=var_df["period"],
                y=var_df["annual_variation_pct"],
                name="Annual Variation (%)",
                marker=dict(
                    color=var_df["annual_variation_pct"].apply(
                        lambda v: PALETTE["green"] if v >= 0 else PALETTE["secondary"]
                    )
                ),
                yaxis="y2",
                hovertemplate="<b>%{x}</b><br>YoY: %{y:.2f}%<extra>Annual Var.</extra>",
                opacity=0.6,
            )
        )

    fig.update_layout(
        yaxis=dict(title="IPV Index", side="left"),
        yaxis2=dict(
            title="Annual Variation (%)",
            side="right",
            overlaying="y",
            showgrid=False,
        ),
        hovermode="x unified",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _apply_defaults(fig, "Housing Price Index (IPV) — Madrid")


# ── Affordability gauge ───────────────────────────────────────────────────────

def affordability_gauge(index_value: float | None) -> go.Figure:
    """Gauge chart showing the affordability index (100 = breakeven)."""
    value = index_value or 0

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=value,
            delta=dict(reference=100, valueformat=".1f"),
            gauge=dict(
                axis=dict(range=[0, 150], tickcolor=PALETTE["muted"]),
                bar=dict(color=PALETTE["primary"]),
                bgcolor=PALETTE["card"],
                bordercolor=PALETTE["border"],
                steps=[
                    dict(range=[0, 60], color="#3d1a1a"),
                    dict(range=[60, 90], color="#3d2e00"),
                    dict(range=[90, 110], color="#1a3d1a"),
                    dict(range=[110, 150], color="#1a2e3d"),
                ],
                threshold=dict(
                    line=dict(color=PALETTE["accent"], width=3),
                    thickness=0.75,
                    value=100,
                ),
            ),
            title=dict(text="Affordability Index<br><sub>100 = just affordable</sub>"),
            number=dict(font=dict(color=PALETTE["text"])),
        )
    )
    fig.update_layout(
        paper_bgcolor=PALETTE["card"],
        font=dict(color=PALETTE["text"]),
        height=260,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


# ── Scatter: price vs rental yield ────────────────────────────────────────────

def price_yield_scatter(data: list[dict]) -> go.Figure:
    """Scatter plot: price/m² (x) vs gross yield (y) per district."""
    if not data:
        return _empty_chart("No data for scatter plot")

    df = pd.DataFrame(data).dropna(subset=["sale_price_m2", "gross_yield_pct"])
    fig = px.scatter(
        df,
        x="sale_price_m2",
        y="gross_yield_pct",
        text="district_name",
        size="rental_price_m2_month",
        color="gross_yield_pct",
        color_continuous_scale="RdYlGn",
        labels={
            "sale_price_m2": "Sale Price (€/m²)",
            "gross_yield_pct": "Gross Yield (%)",
        },
    )
    fig.update_traces(
        textposition="top center",
        textfont=dict(size=9, color=PALETTE["text"]),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Price: %{x:,.0f} €/m²<br>"
            "Yield: %{y:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(coloraxis_showscale=False)
    return _apply_defaults(fig, "Price vs Rental Yield by District")


# ── KPI card ──────────────────────────────────────────────────────────────────

def kpi_figure(value: str, label: str, delta: str = "", positive: bool = True) -> go.Figure:
    """Minimal indicator figure for use in a small card."""
    color = PALETTE["green"] if positive else PALETTE["secondary"]
    fig = go.Figure(
        go.Indicator(
            mode="number+delta" if delta else "number",
            value=None,
            title=dict(text=f"<b>{value}</b><br><sub>{label}</sub>"),
            delta=dict(reference=0, relative=False),
        )
    )
    fig.update_layout(
        paper_bgcolor=PALETTE["card"],
        font=dict(color=PALETTE["text"], size=14),
        height=110,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    return fig


# ── Helpers ────────────────────────────────────────────────────────────────────

def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color=PALETTE["muted"]),
    )
    fig.update_layout(
        paper_bgcolor=PALETTE["card"],
        plot_bgcolor=PALETTE["card"],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig
