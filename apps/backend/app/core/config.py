"""
Core application configuration and environment settings loader.
Reference: ARCHITECTURE.md §11 & TECHSTACK.md
"""

from functools import lru_cache
from typing import Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    """
    Centralized, type-validated application settings loaded from environment
    variables and .env files.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "apps/backend/.env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── Environment & Application ──────────────────────────────────────────
    ENVIRONMENT: str = Field(
        default="development",
        description="Execution environment ('development', 'production', 'test')",
    )
    PROJECT_NAME: str = Field(
        default="Zentrix.ai",
        description="Application name",
    )
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Prefix for API v1 routes",
    )
    API_PORT: int = Field(
        default=8000,
        description="Backend HTTP port",
    )
    CORS_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
        ],
        description="Allowed CORS origin domains",
    )

    # ─── Application Database (PostgreSQL / Neon) ────────────────────────────
    APP_DATABASE_URL: str = Field(
        ...,
        description="Async connection string to application Postgres/Neon DB (e.g. postgresql+asyncpg://user:pass@host:5432/db)",
    )

    @field_validator("APP_DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> Any:
        """
        Ensure the database URL uses postgresql+asyncpg scheme and is compatible
        with asyncpg driver query parameters (e.g. for Neon DB).
        """
        if v is None:
            return v
        if isinstance(v, str):
            url = v.strip()
            if not url:
                return v
            if url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            elif url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            
            # asyncpg uses ssl= rather than sslmode= and doesn't accept channel_binding
            if "channel_binding=" in url:
                import re
                url = re.sub(r"[?&]channel_binding=[^&]+", "", url)
                if "?" not in url and "&" in url:
                    url = url.replace("&", "?", 1)
            if "sslmode=" in url and "ssl=" not in url:
                url = url.replace("sslmode=", "ssl=")
            return url
        return v

    # ─── Authentication & JWT ────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        ...,
        description="Secret key used for signing and verifying JWT authentication tokens",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    JWT_EXPIRY_MINUTES: int = Field(
        default=1440,
        description="JWT token lifetime in minutes (default 24h)",
    )

    DEV_CONNECTIONS_WITHOUT_AUTH: bool = Field(
        default=True,
        description="Allow local development connection and telemetry routes without login",
    )

    # ─── Clerk Authentication Configuration ──────────────────────────────────
    CLERK_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Clerk Secret Key (sk_test_... or sk_live_...)",
    )
    CLERK_ISSUER: Optional[str] = Field(
        default=None,
        description="Clerk Issuer URL (e.g. https://clerk.yourdomain.com or https://...clerk.accounts.dev)",
    )
    CLERK_JWKS_URL: Optional[str] = Field(
        default=None,
        description="Custom Clerk JWKS URL for token public key resolution",
    )
    CLERK_PEM_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="Clerk JWT PEM Public Key for offline RS256 verification",
    )

    # ─── Connection Credential Encryption ────────────────────────────────────
    CONNECTION_ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet key for AES encryption of customer database credentials at rest",
    )

    # ─── MLflow Tracking ─────────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = Field(
        default="http://localhost:5000",
        description="URI of the MLflow tracking server",
    )

    # ─── Worker Configuration ────────────────────────────────────────────────
    TELEMETRY_POLL_INTERVAL_SECONDS: int = Field(
        default=60,
        description="Polling frequency for telemetry collector worker (seconds)",
    )
    CANARY_MONITOR_WINDOW_MINUTES: int = Field(
        default=15,
        description="Observation duration for canary monitor worker (minutes)",
    )
    SHADOW_DB_IMAGE: str = Field(
        default="zentrix-shadow-db:latest",
        description="Docker image used by shadow lab worker for ephemeral testing DBs",
    )

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.lower() == "test"


@lru_cache()
def get_settings() -> Settings:
    """
    Cached accessor returning the singleton Settings instance.
    """
    return Settings()
