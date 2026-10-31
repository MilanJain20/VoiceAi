"""
Application configuration — single source of truth for all settings.

Uses pydantic-settings for type-safe env var parsing with validation.
Settings are loaded once at startup and injected via FastAPI's dependency system.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "123456789"
    postgres_db: str = "voiceai"
    database_url: str = "postgresql+asyncpg://postgres:123456789@localhost:5432/voiceai"

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
    edge_tts_rate: str = "-5%"       # slightly slower for clarity
    edge_tts_volume: str = "+10%"    # a bit louder for presence
    edge_tts_pitch: str = "+0Hz"

    # ---- JWT Auth ----
    jwt_secret_key: str = "voiceai-dev-secret-key-change-in-production-2024"
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
