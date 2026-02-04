"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Database (using psycopg3 for native async without event loop issues)
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/copio"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    access_token_expire_minutes: int = 15  # Short-lived for security
    refresh_token_expire_days: int = 7

    # Amazon SP-API
    amazon_client_id: str = ""
    amazon_client_secret: str = ""
    amazon_refresh_token: str = ""

    # Shopify
    shopify_api_key: str = ""
    shopify_api_secret: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:3000"

    @property
    def async_database_url(self) -> str:
        """Ensure database URL uses psycopg async driver."""
        url = self.database_url
        # Normalize to psycopg for async
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://")
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        return url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
