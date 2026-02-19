"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "dev-secret-key-change-in-production"

    # ── Database ────────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./housing_portal.db"

    # ── INE API ─────────────────────────────────────────────────────────────────
    ine_base_url: str = "https://servicios.ine.es/wstempus/js/ES"
    ine_rate_limit_delay: float = 0.5

    # ── Catastro ────────────────────────────────────────────────────────────────
    catastro_base_url: str = (
        "https://ovc.catastro.meh.es/OVCServCatastro/OVCWCFLibres"
    )

    # ── Idealista ───────────────────────────────────────────────────────────────
    idealista_api_key: str = ""
    idealista_secret: str = ""
    idealista_base_url: str = "https://api.idealista.com/3.5"

    # ── Fotocasa ────────────────────────────────────────────────────────────────
    fotocasa_api_key: str = ""

    # ── Madrid Open Data ────────────────────────────────────────────────────────
    madrid_open_data_url: str = "https://datos.madrid.es/egob/catalogo"

    # ── Scheduler ───────────────────────────────────────────────────────────────
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Madrid"

    # ── Caching ─────────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = 3600
    geojson_cache_path: str = "./static/assets/madrid_districts.geojson"

    # ── Logging ─────────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "./logs/housing_portal.log"

    # ── Derived properties ───────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


# Convenient singleton
settings = get_settings()
