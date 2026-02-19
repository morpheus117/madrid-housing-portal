# 🏠 Madrid Housing Market Portal

A **production-ready Python web portal** for Madrid real-estate analytics — price trends, district comparisons, rental yields, mortgage statistics, and ML-powered price forecasts. Built with **FastAPI + Plotly Dash**, backed by public Spanish institutional data sources.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Plotly Dash](https://img.shields.io/badge/Plotly%20Dash-2.18-3F4F75?logo=plotly&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Data Sources](#data-sources)
6. [API Reference](#api-reference)
7. [Dashboard Tabs](#dashboard-tabs)
8. [Forecasting Models](#forecasting-models)
9. [Database Schema](#database-schema)
10. [Deployment](#deployment)
11. [Development Guide](#development-guide)
12. [API Keys & Rate Limits](#api-keys--rate-limits)
13. [Troubleshooting](#troubleshooting)
14. [Contributing](#contributing)
15. [License](#license)

---

## Features

| Category | Capability |
|---|---|
| **Visualisation** | 10+ interactive Plotly charts, dark Madrid-themed UI |
| **Price Analysis** | Quarterly trends for all 21 Madrid districts, new vs second-hand split |
| **District Map** | Bubble map coloured by price intensity |
| **Rental Market** | Gross yield ranking, price-vs-yield scatter, trend lines |
| **Forecasting** | Ensemble model (SARIMA + Polynomial Regression) with 95% CI |
| **Mortgages** | Volume trends, interest rate / fixed-rate share over time |
| **Affordability** | Gauge index, mortgage-to-income ratio, years-to-buy metric |
| **REST API** | 15+ FastAPI endpoints, auto-generated Swagger docs |
| **Scheduler** | Daily INE data pulls, weekly full refresh — runs in-process |
| **Docker** | Single `docker-compose up` for production deployment |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Browser                                                 │
│  GET /dashboard/  ──► Plotly Dash (interactive UI)       │
│  GET /api/v1/*    ──► FastAPI REST (JSON)                │
│  GET /api/docs    ──► Swagger UI                         │
└──────────────┬───────────────────────────────────────────┘
               │ ASGI (uvicorn)
┌──────────────▼───────────────────────────────────────────┐
│  FastAPI app  (app/main.py)                              │
│  ├─ /api/v1/     APIRouter   (app/api/routes.py)         │
│  └─ /dashboard/  WSGIMiddleware ─► Dash Flask server     │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│  Service Layer                                           │
│  ├─ AnalyticsService   (app/services/analytics.py)       │
│  └─ ForecastingService (app/services/forecasting.py)     │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│  Data Layer                                              │
│  ├─ INEClient        — public REST (no auth required)    │
│  ├─ CatastroClient   — public REST (no auth required)    │
│  ├─ IdealistaClient  — OAuth2 (API key optional)         │
│  └─ DataPipeline     — orchestration + seed data         │
└──────────────┬───────────────────────────────────────────┘
               │ SQLAlchemy ORM
┌──────────────▼───────────────────────────────────────────┐
│  Database (SQLite dev / PostgreSQL prod)                 │
│  districts · sale_prices · rental_prices                 │
│  housing_price_index · mortgage_data · price_forecasts   │
└──────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115 + Uvicorn |
| Dashboard | Plotly Dash 2.18 + Dash Bootstrap Components |
| Charts | Plotly 5.24 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Forecasting | statsmodels SARIMA + scikit-learn LinearRegression |
| Scheduler | APScheduler 3.10 |
| HTTP clients | requests / httpx |
| Config | pydantic-settings |
| Containerisation | Docker + docker-compose |

---

## Quick Start

### Prerequisites

- Python **3.10+** (3.12 recommended)
- `pip` or a virtual-environment manager (`venv`, `conda`, `uv`)
- Internet access (to pull INE data on first run)

### 1 — Clone & enter the project

```bash
git clone https://github.com/YOUR_USERNAME/madrid-housing-portal.git
cd madrid-housing-portal
```

### 2 — Create a virtual environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure the environment

```bash
cp .env.example .env
# Edit .env if you want PostgreSQL or have API keys
```

The default `.env` uses **SQLite** — no database server required.

### 5 — Start the portal

```bash
python run.py
```

On first launch the app will:
1. Create the SQLite database and all tables
2. Seed **realistic synthetic data** for all 21 Madrid districts (2019 Q1 → 2025 Q4)
3. Attempt to fetch live data from the INE API
4. Generate price forecasts for all districts
5. Download the Madrid districts GeoJSON for map visualisation

Open your browser:

| URL | Description |
|---|---|
| `http://localhost:8000/dashboard/` | Interactive dashboard |
| `http://localhost:8000/api/docs` | Swagger / OpenAPI docs |
| `http://localhost:8000/api/redoc` | ReDoc API docs |
| `http://localhost:8000/health` | Health check endpoint |

---

## Configuration

All settings live in `.env` (copy from `.env.example`):

```dotenv
# ── Core ─────────────────────────────────────────────
APP_ENV=development          # development | production
APP_PORT=8000
DATABASE_URL=sqlite:///./housing_portal.db

# ── Switch to PostgreSQL for production ───────────────
# DATABASE_URL=postgresql://user:pass@localhost:5432/housing_portal

# ── INE API (no key needed) ───────────────────────────
INE_RATE_LIMIT_DELAY=0.5     # seconds between requests

# ── Idealista (optional) ──────────────────────────────
IDEALISTA_API_KEY=           # leave blank to use demo data
IDEALISTA_SECRET=

# ── Scheduler ─────────────────────────────────────────
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=Europe/Madrid

# ── Logging ───────────────────────────────────────────
LOG_LEVEL=INFO
```

### Environment reference

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` enables hot-reload; `production` disables it |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Bind port |
| `DATABASE_URL` | SQLite file | SQLAlchemy connection string |
| `INE_BASE_URL` | INE public URL | Override for proxy/testing |
| `INE_RATE_LIMIT_DELAY` | `0.5` | Seconds between INE API calls |
| `IDEALISTA_API_KEY` | _(blank)_ | Idealista OAuth2 key |
| `IDEALISTA_SECRET` | _(blank)_ | Idealista OAuth2 secret |
| `SCHEDULER_ENABLED` | `true` | Disable to run without background jobs |
| `SCHEDULER_TIMEZONE` | `Europe/Madrid` | Timezone for cron jobs |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `GEOJSON_CACHE_PATH` | `./static/assets/madrid_districts.geojson` | Local GeoJSON cache |

---

## Data Sources

### INE — Instituto Nacional de Estadística *(primary, public, no auth)*

| Dataset | INE Operation | Update Frequency | Portal Use |
|---|---|---|---|
| IPV — Housing Price Index | `IPV` (table 25171) | Quarterly | Price index, YoY/QoQ change |
| EH — Mortgage Statistics | `HIP` (table 18862) | Monthly | Mortgage volume & amounts |

**API base:** `https://servicios.ine.es/wstempus/js/ES`
**Rate limit:** No official limit; the portal applies a 0.5 s delay between requests.
**Docs:** [INE DataLab](https://www.ine.es/dyngs/DataLab/manual.html?cid=45)

### Catastro — Sede Electrónica del Catastro *(public, no auth)*

| Service | Endpoint | Portal Use |
|---|---|---|
| Property by coordinates | `OVCCoordenadas` | Point-level cadastral data |
| Municipality info | `OVCCallejero` | Urban-use breakdown |

**API base:** `https://ovc.catastro.meh.es/OVCServCatastro/OVCWCFLibres`
**Docs:** [Catastro Web Services](https://www.catastro.meh.es/ws/)

### Idealista *(optional — requires free API key)*

| Endpoint | Data |
|---|---|
| `/sale/homes/search` | Sale listings |
| `/rentals/homes/search` | Rental listings |

**Register:** [developers.idealista.com](https://developers.idealista.com/)
**Auth:** OAuth2 client_credentials
**Free tier:** 100 searches/month
**Fallback:** When no credentials are configured the portal uses the built-in synthetic dataset — all features remain functional.

### Madrid Open Data Portal

| Dataset | URL | Portal Use |
|---|---|---|
| Districts GeoJSON | `datos.madrid.es/egob/catalogo/200078-0-distritos.geojson` | District map |

### Demo / Synthetic Data

When live APIs are unavailable the pipeline seeds **realistic synthetic data** derived from known Madrid market statistics:

- City-wide quarterly prices: 2019 Q1 → 2025 Q4
- Per-district price multipliers calibrated to real 2024 values (e.g. Salamanca 1.40×, Villaverde 0.60×)
- Rental prices derived from sale prices at ~3.0% gross yield
- Mortgage data with COVID-period dip (2020 Q2) and post-2022 rate rise

---

## API Reference

Full interactive docs at `http://localhost:8000/api/docs`.

### Endpoints summary

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/districts` | List all 21 districts |
| `GET` | `/api/v1/districts/{code}` | Single district by code |
| `GET` | `/api/v1/summary` | Market KPI snapshot |
| `GET` | `/api/v1/prices/trends` | Quarterly price trend |
| `GET` | `/api/v1/prices/snapshot` | Per-district price for a period |
| `GET` | `/api/v1/rental/analysis` | Rental prices + gross yields |
| `GET` | `/api/v1/ipv` | INE Housing Price Index series |
| `GET` | `/api/v1/mortgages` | Monthly mortgage statistics |
| `GET` | `/api/v1/forecast/{district_code}` | Price forecast for a district |
| `POST` | `/api/v1/forecast/run-all` | Trigger all-district forecasting |
| `GET` | `/api/v1/affordability` | Affordability metrics |
| `POST` | `/api/v1/data/refresh` | Trigger full data refresh |
| `POST` | `/api/v1/data/seed` | Re-seed demo data |

### Example calls

```bash
# Market summary
curl http://localhost:8000/api/v1/summary | jq .

# Price trend for Salamanca district (code 04), since 2021
curl "http://localhost:8000/api/v1/prices/trends?district=04&from_year=2021" | jq .

# Rental analysis (current period)
curl http://localhost:8000/api/v1/rental/analysis | jq .

# 12-quarter ensemble forecast for Chamberí (code 07)
curl "http://localhost:8000/api/v1/forecast/07?periods=12&model=ensemble" | jq .

# Trigger background data refresh
curl -X POST http://localhost:8000/api/v1/data/refresh
```

### District codes

| Code | District | Code | District |
|---|---|---|---|
| `01` | Centro | `12` | Usera |
| `02` | Arganzuela | `13` | Puente de Vallecas |
| `03` | Retiro | `14` | Moratalaz |
| `04` | Salamanca | `15` | Ciudad Lineal |
| `05` | Chamartín | `16` | Hortaleza |
| `06` | Tetuán | `17` | Villaverde |
| `07` | Chamberí | `18` | Villa de Vallecas |
| `08` | Fuencarral-El Pardo | `19` | Vicálvaro |
| `09` | Moncloa-Aravaca | `20` | San Blas-Canillejas |
| `10` | Latina | `21` | Barajas |
| `11` | Carabanchel | | |

---

## Dashboard Tabs

### Overview
- KPI cards: avg sale price/m², YoY change, rental price, gross yield
- City-wide price trend line chart
- Housing Price Index (IPV) chart with annual variation bars
- District price bar chart (all 21 districts)

### Price Trends
- Multi-series quarterly trend with district / property-type filters
- New construction vs second-hand comparison
- Detailed IPV chart with dual axes

### Districts
- Interactive bubble map — bubble size and colour encode price/m²
- Horizontal bar chart ranked by price
- Sortable / filterable data table

### Rental Market
- Gross yield bar chart (colour-coded: green ≥4%, amber ≥3%, red <3%)
- Price-vs-yield scatter plot (bubble size = rental price)
- Rental price trend

### Forecasting
- Historical + ensemble forecast line with 95% confidence interval shading
- Affordability gauge (100 = just affordable at average Madrid income)
- Affordability metrics panel
- Downloadable forecast table

### Mortgage Market
- Monthly mortgage volume area chart
- Dual-axis chart: average interest rate + fixed-rate share
- Latest-period stats panel

---

## Forecasting Models

### 1. Linear (Polynomial) Regression — baseline

- Fits a degree-2 polynomial on the quarterly price series
- Confidence interval derived from residual standard deviation
- Used as fallback when SARIMA fails

### 2. SARIMA — Seasonal ARIMA

- Order: `(1,1,1)(1,1,0,4)` — quarterly seasonality (m=4)
- Fitted via `statsmodels.tsa.statespace.SARIMAX`
- Requires ≥12 observations; falls back to linear otherwise
- 95% confidence interval from the model's forecast distribution

### 3. Ensemble *(default)*

- Weighted average: **65% SARIMA + 35% Linear**
- Combines SARIMA's seasonal pattern capture with regression's trend stability
- Confidence bounds blended with the same weights

All forecasts are stored in the `price_forecasts` table and retrieved on subsequent requests (no re-computation cost).

---

## Database Schema

```
districts
  id, code (PK candidate), name, name_es,
  latitude, longitude, area_km2, population

sale_prices
  id, district_id → districts,
  year, quarter, price_per_m2,
  property_type (all|new|second_hand),
  transactions, source
  UNIQUE(district_id, year, quarter, property_type)

rental_prices
  id, district_id → districts,
  year, quarter, price_per_m2_month,
  listings_count, source
  UNIQUE(district_id, year, quarter)

housing_price_index      ← INE IPV
  id, year, quarter,
  property_type, index_value,
  annual_variation_pct, quarterly_variation_pct,
  source
  UNIQUE(year, quarter, property_type)

mortgage_data            ← INE EH
  id, year, month,
  num_mortgages, avg_amount_eur,
  avg_interest_rate, fixed_rate_pct,
  avg_duration_years, source
  UNIQUE(year, month)

price_forecasts
  id, district_id → districts,
  model_name, forecast_year, forecast_quarter,
  predicted_price_m2, lower_bound, upper_bound,
  confidence_level, generated_at
  UNIQUE(district_id, forecast_year, forecast_quarter, model_name)

data_fetch_log
  id, source, endpoint, status,
  records_fetched, error_message,
  started_at, finished_at
```

---

## Deployment

### Option A — Local development

```bash
python run.py                  # hot-reload, SQLite
python run.py --port 9000      # custom port
python run.py --prod           # no hot-reload
```

### Option B — Docker Compose (PostgreSQL)

```bash
# 1. Set production secrets in .env
cp .env.example .env
# Edit: set APP_ENV=production, DATABASE_URL=postgresql://...

# 2. Build and start
docker-compose up --build -d

# 3. Tail logs
docker-compose logs -f app

# 4. Stop
docker-compose down
```

The `docker-compose.yml` starts:
- `app` — FastAPI/Dash on port 8000
- `db` — PostgreSQL 16 with health check

### Option C — Manual production (systemd)

```bash
# Install as a system service
pip install -r requirements.txt
APP_ENV=production DATABASE_URL="postgresql://..." \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

> **Note:** Dash's Flask server is not thread-safe with multiple Uvicorn workers.
> Use `--workers 1` or place a reverse proxy (nginx) in front.

### Option D — Cloud (Render / Railway / Fly.io)

```bash
# Render / Railway — set env vars in dashboard, run:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Fly.io
fly launch && fly secrets set DATABASE_URL="postgresql://..."
fly deploy
```

### Reverse proxy (nginx) — recommended for production

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

---

## Development Guide

### Project layout

```
housing_portal/
├── run.py                      ← Entry point
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py                 ← App factory + lifespan
│   ├── config.py               ← Pydantic Settings
│   ├── database.py             ← SQLAlchemy engine + helpers
│   ├── scheduler.py            ← APScheduler jobs
│   ├── models/
│   │   └── housing.py          ← All ORM models
│   ├── data/
│   │   ├── ine_client.py       ← INE API client
│   │   ├── catastro_client.py  ← Catastro API client
│   │   ├── idealista_client.py ← Idealista API client
│   │   └── pipeline.py         ← Orchestration + seed data
│   ├── services/
│   │   ├── analytics.py        ← Analytics computations
│   │   └── forecasting.py      ← ML forecasting
│   ├── api/
│   │   ├── schemas.py          ← Pydantic schemas
│   │   └── routes.py           ← FastAPI routers
│   └── dashboard/
│       ├── charts.py           ← Plotly chart factories
│       ├── layout.py           ← Dash layout
│       └── callbacks.py        ← Dash callbacks
├── static/assets/
│   └── custom.css              ← Dark theme CSS
└── tests/
    ├── test_analytics.py
    └── test_forecasting.py
```

### Running tests

```bash
pytest tests/ -v
```

### Adding a new data source

1. Create `app/data/my_source_client.py` with a client class
2. Add a fetch method to `DataPipeline` in `app/data/pipeline.py`
3. Add a new SQLAlchemy model if needed in `app/models/housing.py`
4. Run `init_db()` (or an Alembic migration) to create the table
5. Add an API endpoint in `app/api/routes.py`
6. Add a chart in `app/dashboard/charts.py` and wire a callback

### Adding a new dashboard chart

1. Write a chart factory function in `app/dashboard/charts.py`
2. Add an `html.Div(dcc.Graph(id="my-new-chart"))` in the relevant tab in `app/dashboard/layout.py`
3. Register an `@app.callback(Output("my-new-chart", "figure"), ...)` in `app/dashboard/callbacks.py`

### Applying database migrations (Alembic)

```bash
pip install alembic

# Initialise (first time only)
alembic init alembic

# Generate a migration from model changes
alembic revision --autogenerate -m "add_my_field"

# Apply
alembic upgrade head
```

---

## API Keys & Rate Limits

| Source | Auth required | Rate limit | How to get |
|---|---|---|---|
| INE | None | ~10 req/s (unofficial) | n/a — public API |
| Catastro | None | None published | n/a — public API |
| Idealista | OAuth2 key+secret | 100 searches/month (free) | [developers.idealista.com](https://developers.idealista.com/) |
| Fotocasa | Partner agreement | Varies | [Schibsted Media Group](https://www.schibsted.com/) |
| Madrid Open Data | None | None | n/a — public |

### Compliance notes

- **INE data** is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — attribution required.
- **Catastro data** is published under [INSPIRE Directive / Open Government Licence](https://www.catastro.meh.es/).
- **Idealista API** — usage governed by Idealista's [API Terms of Service](https://developers.idealista.com/). Scraping without an API key violates their ToS.
- Always check current licensing terms before using data in production.

---

## Troubleshooting

### Portal starts but dashboard is blank

The database may be empty. Seed it manually:

```bash
python run.py --seed-only
# or via API:
curl -X POST http://localhost:8000/api/v1/data/seed
```

### INE / Catastro API returns no data

The INE API occasionally times out or returns empty results. The pipeline logs a `skipped` status in `data_fetch_log` and the portal falls back to existing data. Check connectivity:

```bash
curl "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/25171?nult=2"
```

### Map shows dots instead of district polygons

The districts GeoJSON download failed. Either:
- Re-trigger it: `curl -X POST http://localhost:8000/api/v1/data/refresh`
- Download manually: `curl -o static/assets/madrid_districts.geojson https://datos.madrid.es/egob/catalogo/200078-0-distritos.geojson`

### `ModuleNotFoundError` on startup

Ensure your virtual environment is active and dependencies are installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### SQLite `database is locked`

SQLite WAL mode is enabled automatically, but if you see lock errors under concurrent load, migrate to PostgreSQL:

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/housing_portal
```

### Port already in use

```bash
python run.py --port 9000
# or
APP_PORT=9000 python run.py
```

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

### Commit message convention

```
feat:     new feature
fix:      bug fix
refactor: code change without feature/fix
docs:     documentation changes
test:     test additions/changes
chore:    build, CI, dependency updates
```

---

## License

MIT © 2025 — see [LICENSE](LICENSE) for details.

Data from INE is published under CC BY 4.0. Data from Catastro is published under the Spanish Open Government Licence. Idealista data requires a valid API agreement.

---

*Built with ❤️ for the Madrid real-estate analytics community.*
