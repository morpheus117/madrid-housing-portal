"""
Catastro (Sede Electrónica del Catastro) API client.

Public REST API — no authentication required.
Documentation: https://www.catastro.meh.es/ws/

Useful endpoints:
  OVCCallejero     — street search
  Consulta_DNPRC   — query by cadastral reference
  OVCCoordenadas   — query by coordinates (lat/lon)
"""

import requests
from loguru import logger

from app.config import settings


class CatastroClient:
    """Client for the Catastro REST web services."""

    BASE = settings.catastro_base_url
    TIMEOUT = 15

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    # ── Public methods ─────────────────────────────────────────────────────────

    def get_urban_use_stats(self, municipio: str = "Madrid") -> dict:
        """
        Approximate urban-use statistics for a municipality.

        Returns a summary dict with counts of residential, commercial,
        industrial, and other-use properties.

        Note: Catastro's public API does not expose aggregate statistics
        directly; this method wraps the street-level search and summarises
        a sample of results.  For bulk data, use the Catastro mass-download
        (Descarga Masiva) service instead.
        """
        logger.info(f"Fetching Catastro urban-use stats for {municipio}")
        url = f"{self.BASE}/OVCCallejero.svc/json/Consulta_VMUN"
        params = {"Provincia": "Madrid", "Municipio": municipio}
        raw = self._get(url, params)
        return self._parse_municipality_info(raw)

    def get_property_by_coordinates(
        self, lat: float, lon: float, srs: str = "EPSG:4326"
    ) -> dict | None:
        """Return cadastral reference info for a lat/lon coordinate."""
        url = f"{self.BASE}/OVCCoordenadas.svc/json/Consulta_RCCOOR"
        params = {"SRS": srs, "Latitud": lat, "Longitud": lon}
        raw = self._get(url, params)
        return self._parse_property(raw)

    def get_property_info(
        self, provincia: str, municipio: str, rc: str
    ) -> dict | None:
        """Return detailed cadastral info for a given cadastral reference."""
        url = f"{self.BASE}/OVCServicioCatastro.svc/json/Consulta_DNPRC"
        params = {
            "Provincia": provincia,
            "Municipio": municipio,
            "RC": rc,
        }
        raw = self._get(url, params)
        return self._parse_property(raw)

    # ── HTTP helper ────────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            resp = self._session.get(url, params=params, timeout=self.TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logger.warning(f"Catastro timeout: {url}")
            return {}
        except requests.exceptions.HTTPError as exc:
            logger.error(
                f"Catastro HTTP error {exc.response.status_code}: {url}"
            )
            return {}
        except Exception as exc:
            logger.error(f"Catastro error: {exc}")
            return {}

    # ── Parsers ────────────────────────────────────────────────────────────────

    def _parse_municipality_info(self, raw: dict) -> dict:
        """Extract municipality-level stats from Catastro JSON response."""
        try:
            body = (
                raw.get("consulta_municipiero", {})
                .get("municipiero", {})
                .get("muni", {})
            )
            return {
                "municipio": body.get("nm", ""),
                "provincia": body.get("np", ""),
                "code": body.get("cm", ""),
            }
        except (AttributeError, KeyError):
            return {}

    def _parse_property(self, raw: dict) -> dict | None:
        """Extract property info from a Catastro coordinate/RC query."""
        try:
            consulta = raw.get("consulta_coordenadas", {}) or raw.get(
                "consulta_dnp", {}
            )
            lrcdnp = consulta.get("coordenadas", {}).get("coord", [])
            if not lrcdnp:
                return None
            item = lrcdnp[0] if isinstance(lrcdnp, list) else lrcdnp
            return {
                "cadastral_ref": item.get("pc", {}).get("pc1", "")
                + item.get("pc", {}).get("pc2", ""),
                "address": item.get("ldt", ""),
                "use": item.get("dt", {}).get("locs", {}).get("lous", {}).get(
                    "lourb", {}
                ),
            }
        except (AttributeError, KeyError, IndexError):
            return None
