"""
Unit tests for application configuration and environment loader.
Step 3 verification: settings loading, validation, and error handling.
"""

import os
import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings


def test_settings_load_successfully():
    """Verify that settings can be loaded from .env or environment."""
    settings = get_settings()
    assert settings.APP_DATABASE_URL is not None
    assert settings.JWT_SECRET_KEY is not None
    assert settings.CONNECTION_ENCRYPTION_KEY is not None
    assert settings.ENVIRONMENT in ["development", "production", "test"]
    assert settings.API_PORT > 0
    assert settings.JWT_EXPIRY_MINUTES > 0
    assert settings.TELEMETRY_POLL_INTERVAL_SECONDS > 0
    assert settings.CANARY_MONITOR_WINDOW_MINUTES > 0
    assert settings.SHADOW_DB_IMAGE != ""
    assert settings.MLFLOW_TRACKING_URI != ""


def test_settings_custom_values():
    """Verify that settings accept valid custom values directly."""
    custom = Settings(
        APP_DATABASE_URL="postgresql+asyncpg://admin:secret@db.neon.tech/custom_db",
        JWT_SECRET_KEY="super-secret-custom-key-12345678",
        CONNECTION_ENCRYPTION_KEY="custom-fernet-key-32-bytes-long-123=",
        ENVIRONMENT="production",
        TELEMETRY_POLL_INTERVAL_SECONDS=30,
        CANARY_MONITOR_WINDOW_MINUTES=20,
        SHADOW_DB_IMAGE="zentrix-shadow:v2",
        _env_file=None,
    )
    assert custom.APP_DATABASE_URL == "postgresql+asyncpg://admin:secret@db.neon.tech/custom_db"
    assert custom.ENVIRONMENT == "production"
    assert custom.is_production is True
    assert custom.is_development is False
    assert custom.TELEMETRY_POLL_INTERVAL_SECONDS == 30
    assert custom.CANARY_MONITOR_WINDOW_MINUTES == 20
    assert custom.SHADOW_DB_IMAGE == "zentrix-shadow:v2"


def test_missing_required_database_url_raises_validation_error():
    """Verify that missing APP_DATABASE_URL raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_DATABASE_URL=None,  # type: ignore
            JWT_SECRET_KEY="some-key",
            CONNECTION_ENCRYPTION_KEY="some-fernet-key",
            _env_file=None,
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("APP_DATABASE_URL",) for err in errors)


def test_missing_required_jwt_key_raises_validation_error():
    """Verify that missing JWT_SECRET_KEY raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            JWT_SECRET_KEY=None,  # type: ignore
            CONNECTION_ENCRYPTION_KEY="some-fernet-key",
            _env_file=None,
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("JWT_SECRET_KEY",) for err in errors)


def test_missing_required_encryption_key_raises_validation_error():
    """Verify that missing CONNECTION_ENCRYPTION_KEY raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            JWT_SECRET_KEY="some-key",
            CONNECTION_ENCRYPTION_KEY=None,  # type: ignore
            _env_file=None,
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("CONNECTION_ENCRYPTION_KEY",) for err in errors)


def test_cached_singleton_instance():
    """Verify get_settings() returns a cached singleton instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
