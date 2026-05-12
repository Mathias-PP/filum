from __future__ import annotations

import os
import secrets
from typing import Any

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

    database_url: str = "postgresql+asyncpg://filum:changeme@localhost:5432/filum_dev"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    session_secret: str = ""
    master_encryption_key: str = ""

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

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._validate_secrets()

    def _validate_secrets(self) -> None:
        if not self.session_secret:
            self.session_secret = secrets.token_urlsafe(32)
        if not self.master_encryption_key:
            self.master_encryption_key = secrets.token_hex(32)

        if self.debug and os.environ.get("CI") != "true":
            import logging
            logging.warning(
                "Application started with default or weak secrets. "
                "In production, always use strong secrets from environment variables."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
