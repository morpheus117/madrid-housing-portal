"""
Idealista API client.

Requires registration at: https://developers.idealista.com/
Authentication: OAuth 2.0 (client_credentials grant).

Rate limits (free tier):
  - 100 searches/month
  - Results per page: up to 50

This module implements the full client but gracefully degrades to returning
an empty payload when credentials are not configured.
"""

import base64
from datetime import datetime, timedelta

import requests
from loguru import logger

from app.config import settings


class IdealistaClient:
    """OAuth2-authenticated Idealista API client."""

    BASE = settings.idealista_base_url
    TOKEN_URL = "https://api.idealista.com/oauth/token"
    TIMEOUT = 15

    def __init__(self) -> None:
        self._session = requests.Session()
        self._access_token: str | None = None
        self._token_expiry: datetime = datetime.min
        self._configured = bool(
            settings.idealista_api_key and settings.idealista_secret
        )
        if not self._configured:
            logger.warning(
                "Idealista credentials not set — client will return empty data. "
                "Set IDEALISTA_API_KEY and IDEALISTA_SECRET in .env to enable."
            )

    # ── Public methods ─────────────────────────────────────────────────────────

    def search_sale_listings(
        self,
        location: str = "0-EU-ES-28-07-001-079",  # Madrid municipality
        property_type: str = "homes",
        max_items: int = 50,
        **kwargs,
    ) -> list[dict]:
        """Search for sale listings in a location."""
        if not self._configured:
            return []
        return self._search(
            "sale", location, property_type, max_items, **kwargs
        )

    def search_rental_listings(
        self,
        location: str = "0-EU-ES-28-07-001-079",
        property_type: str = "homes",
        max_items: int = 50,
        **kwargs,
    ) -> list[dict]:
        """Search for rental listings in a location."""
        if not self._configured:
            return []
        return self._search(
            "rentals", location, property_type, max_items, **kwargs
        )

    def get_price_trends(
        self,
        location: str = "0-EU-ES-28-07-001-079",
        operation: str = "sale",
    ) -> dict:
        """
        Retrieve price trend data for a location (if available in your plan).

        Note: price-trend endpoints may require a paid API tier.
        """
        if not self._configured:
            return {}
        token = self._get_token()
        if not token:
            return {}
        url = f"{self.BASE}/es/{operation}/homes/{location}/trend"
        return self._get(url, token) or {}

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def _get_token(self) -> str | None:
        """Return a valid access token, refreshing if expired."""
        if self._access_token and datetime.utcnow() < self._token_expiry:
            return self._access_token
        return self._fetch_token()

    def _fetch_token(self) -> str | None:
        """Request a new client_credentials token from Idealista."""
        credentials = base64.b64encode(
            f"{settings.idealista_api_key}:{settings.idealista_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials", "scope": "read"}
        try:
            resp = requests.post(
                self.TOKEN_URL, headers=headers, data=data, timeout=self.TIMEOUT
            )
            resp.raise_for_status()
            payload = resp.json()
            self._access_token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 3600))
            self._token_expiry = datetime.utcnow() + timedelta(
                seconds=expires_in - 30
            )
            logger.info("Idealista: access token refreshed.")
            return self._access_token
        except Exception as exc:
            logger.error(f"Idealista token error: {exc}")
            return None

    # ── Search helper ──────────────────────────────────────────────────────────

    def _search(
        self,
        operation: str,
        location: str,
        property_type: str,
        max_items: int,
        **kwargs,
    ) -> list[dict]:
        token = self._get_token()
        if not token:
            return []
        url = f"{self.BASE}/es/{operation}/{property_type}/search"
        params = {
            "locationId": location,
            "maxItems": min(max_items, 50),
            "numPage": 1,
            "language": "en",
            **kwargs,
        }
        raw = self._post(url, token, params)
        return raw.get("elementList", []) if raw else []

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    def _get(self, url: str, token: str, params: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = self._session.get(
                url, headers=headers, params=params, timeout=self.TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"Idealista GET error: {exc}")
            return {}

    def _post(
        self, url: str, token: str, data: dict | None = None
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            resp = self._session.post(
                url, headers=headers, data=data, timeout=self.TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"Idealista POST error: {exc}")
            return {}
