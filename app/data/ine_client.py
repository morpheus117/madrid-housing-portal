"""
INE (Instituto Nacional de Estadística) API client.

Public JSON API — no authentication required.
Rate limit: respect ine_rate_limit_delay between requests.

Key resources:
  https://www.ine.es/dyngs/DataLab/manual.html?cid=45

Notable table IDs used here:
  25171  — IPV: Quarterly index by Comunidad Autónoma (general)
  25174  — IPV: Annual variation by Comunidad Autónoma
  18862  — EH (Hipotecas): Monthly mortgages on housing by province
"""

import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from app.config import settings


class INEClient:
    """Thin wrapper around the INE public JSON API."""

    BASE = settings.ine_base_url
    TIMEOUT = 20  # seconds

    # Mapping from Comunidad Autónoma name to madrid code in INE data
    MADRID_CA_CODE = "13"  # Comunidad de Madrid in INE tables

    # ── Table IDs ──────────────────────────────────────────────────────────────
    IPV_GENERAL_TABLE = "25171"       # IPV general quarterly index
    IPV_VARIATION_TABLE = "25174"     # IPV annual / quarterly variation
    MORTGAGE_MADRID_TABLE = "18862"   # EH mortgages by province (Madrid=28)

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._last_request: float = 0.0

    # ── Public methods ─────────────────────────────────────────────────────────

    def get_housing_price_index(self, n_periods: int = 20) -> list[dict]:
        """
        Fetch the IPV (Índice de Precios de Vivienda) for Comunidad de Madrid.

        Returns a list of dicts with keys:
          year, quarter, index_value, annual_variation_pct,
          quarterly_variation_pct, property_type
        """
        raw = self._fetch_table(self.IPV_GENERAL_TABLE, n_periods)
        return self._parse_ipv(raw)

    def get_housing_price_variation(self, n_periods: int = 20) -> list[dict]:
        """Fetch IPV annual and quarterly variation table."""
        raw = self._fetch_table(self.IPV_VARIATION_TABLE, n_periods)
        return self._parse_ipv_variation(raw)

    def get_mortgage_stats(self, n_periods: int = 36) -> list[dict]:
        """
        Fetch monthly mortgage statistics for Madrid province (code 28).

        Returns a list of dicts with keys:
          year, month, num_mortgages, avg_amount_eur
        """
        raw = self._fetch_table(self.MORTGAGE_MADRID_TABLE, n_periods)
        return self._parse_mortgages(raw)

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    def _fetch_table(self, table_id: str, n_last: int) -> list[dict]:
        """Fetch the last *n_last* periods of an INE table."""
        url = f"{self.BASE}/DATOS_TABLA/{table_id}"
        params = {"nult": n_last}
        return self._get(url, params)

    def _fetch_series(self, series_code: str, n_last: int) -> list[dict]:
        """Fetch the last *n_last* values of an INE series."""
        url = f"{self.BASE}/DATOS_SERIE/{series_code}"
        params = {"nult": n_last}
        return self._get(url, params)

    def _get(self, url: str, params: dict | None = None) -> list[dict]:
        """Make a rate-limited GET request and return parsed JSON."""
        self._rate_limit()
        try:
            resp = self._session.get(url, params=params, timeout=self.TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            # INE returns either a list or a dict with a 'Data' key
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "Data" in data:
                return data["Data"]
            return data if isinstance(data, list) else []
        except requests.exceptions.Timeout:
            logger.warning(f"INE timeout: {url}")
            return []
        except requests.exceptions.HTTPError as exc:
            logger.error(f"INE HTTP error {exc.response.status_code}: {url}")
            return []
        except Exception as exc:
            logger.error(f"INE unexpected error: {exc}")
            return []

    def _rate_limit(self) -> None:
        """Ensure minimum delay between consecutive requests."""
        elapsed = time.monotonic() - self._last_request
        wait = settings.ine_rate_limit_delay - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    # ── Parsers ────────────────────────────────────────────────────────────────

    def _parse_ipv(self, raw: list[dict]) -> list[dict]:
        """
        Parse IPV table rows.  INE JSON structure:
          [{"COD": ..., "Nombre": "...", "Data": [...]}]
        Each Data point has: Anyo, Fecha (epoch ms), Valor
        Madrid series are labelled "Madrid, Comunidad de. <type>. Índice."
        """
        from datetime import datetime, timezone

        results: list[dict] = []
        for series in raw:
            nombre: str = series.get("Nombre", "")
            # Keep only Comunidad de Madrid index series (not variation series)
            if "Madrid, Comunidad de" not in nombre:
                continue
            if "Índice" not in nombre:
                continue

            nombre_lower = nombre.lower()
            prop_type = "all"
            if "nueva" in nombre_lower:
                prop_type = "new"
            elif "segunda" in nombre_lower:
                prop_type = "second_hand"

            for point in series.get("Data", []):
                try:
                    value = point.get("Valor")
                    if value is None:
                        continue
                    # Derive year and quarter from Fecha (epoch milliseconds)
                    fecha_ms = point.get("Fecha")
                    if fecha_ms is None:
                        continue
                    dt = datetime.fromtimestamp(fecha_ms / 1000, tz=timezone.utc)
                    year = dt.year
                    quarter = (dt.month - 1) // 3 + 1
                    results.append(
                        {
                            "year": year,
                            "quarter": quarter,
                            "index_value": float(value),
                            "property_type": prop_type,
                            "annual_variation_pct": None,
                            "quarterly_variation_pct": None,
                        }
                    )
                except (ValueError, TypeError):
                    continue
        return results

    def _parse_ipv_variation(self, raw: list[dict]) -> list[dict]:
        """Parse IPV variation table — similar structure to _parse_ipv."""
        return self._parse_ipv(raw)  # structure identical; Valor = variation %

    def _parse_mortgages(self, raw: list[dict]) -> list[dict]:
        """Parse EH mortgage table for Madrid (province code 28)."""
        results: list[dict] = []
        for series in raw:
            nombre: str = series.get("Nombre", "")
            # Only Madrid province (28)
            if "Madrid" not in nombre:
                continue
            # Only total / number of mortgages series
            if "número" not in nombre.lower() and "number" not in nombre.lower():
                if "importe" not in nombre.lower():
                    continue

            is_count = "número" in nombre.lower() or "number" in nombre.lower()

            for point in series.get("Data", []):
                try:
                    year = int(point.get("Anyo", 0))
                    month = int(point.get("FK_Periodo", 1))
                    value = point.get("Valor")
                    if year and month and value is not None:
                        entry = {"year": year, "month": month}
                        if is_count:
                            entry["num_mortgages"] = int(float(value))
                        else:
                            entry["avg_amount_eur"] = float(value)
                        results.append(entry)
                except (ValueError, TypeError):
                    continue
        return results

    @staticmethod
    def _parse_quarter(nk: str) -> int | None:
        """Extract quarter number (1-4) from INE period code."""
        import re
        match = re.search(r"(\d)", nk)
        if match:
            q = int(match.group(1))
            return q if 1 <= q <= 4 else None
        return None
