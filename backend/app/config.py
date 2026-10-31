"""
Application configuration — single source of truth for all settings.

Uses pydantic-settings for type-safe env var parsing with validation.
Settings are loaded once at startup and injected via FastAPI's dependency system.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Root of the backend package (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Root of the monorepo
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_log_level: str = "DEBUG"

    # ---- Backend Server ----
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 1
    backend_cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # ---- PostgreSQL ----
    # No password default. Set POSTGRES_PASSWORD or DATABASE_URL (see .env.example).
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "voiceai"
    postgres_password: str = ""
    postgres_db: str = "voiceai"
    database_url: str = ""

    # ---- Redis (optional — uses in-memory store if disabled) ----
    use_redis: bool = False
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_url: str = "redis://localhost:6379/0"

    # ---- Azure OpenAI ----
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_max_tokens: int = 4096
    azure_openai_temperature: float = 0.2

    # ---- Deepgram ----
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-2"
    deepgram_language: str = "en-US"
    deepgram_sample_rate: int = 16000

    # ---- Edge TTS (free, no API key) ----
    edge_tts_voice: str = "en-US-AriaNeural"
    edge_tts_rate: str = "-5%"  # slightly slower for clarity
    edge_tts_volume: str = "+10%"  # a bit louder for presence
    edge_tts_pitch: str = "+0Hz"

    # ---- TLS ----
    # Off by default. Set true only when an intercepting proxy breaks
    # Deepgram or Edge TTS certificate checks. Do not enable in production.
    insecure_skip_tls_verify: bool = False

    # ---- JWT Auth ----
    # Empty in development generates an ephemeral secret for this process.
    # Staging and production must set JWT_SECRET_KEY.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    auth_enabled: bool = False  # Set True to enforce auth on all routes

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v

    @model_validator(mode="after")
    def resolve_secrets(self) -> Self:
        """Require a database credential from the environment.

        JWT may be generated per process in development. Staging and
        production refuse to start without JWT_SECRET_KEY.
        """
        if not self.database_url:
            if not self.postgres_password:
                raise ValueError(
                    "Set DATABASE_URL or POSTGRES_PASSWORD. "
                    "Copy .env.example to .env for local development."
                )
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )

        if not self.jwt_secret_key:
            if self.app_env != "development":
                raise ValueError(
                    "JWT_SECRET_KEY is required when APP_ENV is staging or production."
                )
            self.jwt_secret_key = secrets.token_urlsafe(32)
            logger.warning(
                "JWT_SECRET_KEY is unset; generated an ephemeral development secret. "
                "Tokens will not survive a process restart."
            )
        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — loaded once per process."""
    return Settings()
