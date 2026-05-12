from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = "Filum API"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://filum:filum_dev_password@localhost:5432/filum_dev"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    session_secret: str = "change-me-with-openssl-rand-hex-32"
    master_encryption_key: str = "change-me-with-openssl-rand-hex-32"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    frontend_base_url: str = "http://localhost:5173"
    backend_base_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_per_minute: int = 60

    wayback_api_key: str = ""

    duckdb_path: str = "/data/filum_analytics.duckdb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
