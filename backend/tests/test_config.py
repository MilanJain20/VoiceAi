"""Settings must not ship with a database password or JWT secret."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_development_generates_jwt_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://voiceai:voiceai_dev_password@localhost:5432/voiceai",
    )
    monkeypatch.setenv("JWT_SECRET_KEY", "")

    settings = Settings()

    assert len(settings.jwt_secret_key) >= 32
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_production_requires_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://voiceai:voiceai_dev_password@localhost:5432/voiceai",
    )
    monkeypatch.setenv("JWT_SECRET_KEY", "")

    with pytest.raises(ValidationError):
        Settings()


def test_missing_database_credential_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-not-for-production-use")

    with pytest.raises(ValidationError):
        Settings()


def test_database_url_is_built_from_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("POSTGRES_USER", "voiceai")
    monkeypatch.setenv("POSTGRES_PASSWORD", "voiceai_dev_password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "voiceai")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-not-for-production-use")

    settings = Settings()

    assert settings.database_url == (
        "postgresql+asyncpg://voiceai:voiceai_dev_password@localhost:5432/voiceai"
    )
